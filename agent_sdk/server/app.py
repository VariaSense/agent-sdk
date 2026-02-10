import logging
import asyncio
import os
from dataclasses import asdict
from typing import Optional
from fastapi import FastAPI, Depends, HTTPException, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse, Response
from fastapi.responses import StreamingResponse
from pydantic import ValidationError
from agent_sdk.config.loader import load_config, load_model_names
from agent_sdk.core.runtime import PlannerExecutorRuntime
from agent_sdk.llm.mock import MockLLMClient
from agent_sdk.plugins.loader import PluginLoader
from agent_sdk.security import (
    verify_api_key,
    get_api_key_manager,
    require_scopes,
    SCOPE_ADMIN,
    SCOPE_RUN_READ,
    SCOPE_RUN_WRITE,
    SCOPE_SESSION_READ,
    SCOPE_TOOLS_READ,
    SCOPE_DEVICE_MANAGE,
    SCOPE_CHANNEL_WRITE,
)
from agent_sdk.validators import (
    RunTaskRequest,
    TaskResponse,
    HealthResponse,
    ReadyResponse,
    ChannelMessageRequest,
    APIKeyCreateRequest,
    DeviceRegisterRequest,
    DevicePairRequest,
    ReplayEventsResponse,
    RunEventsDeleteRequest,
    ModelPolicyRequest,
    QuotaUpdateRequest,
    RetentionPolicyRequest,
    ScheduleCreateRequest,
    PromptPolicyCreateRequest,
)
from agent_sdk.exceptions import ConfigError, AgentSDKException
from agent_sdk.observability.stream_envelope import (
    StreamEnvelope,
    StreamChannel,
    RunStatus,
    RunMetadata,
    SessionMetadata,
    new_run_id,
    new_session_id,
)
from agent_sdk.observability.run_logs import create_run_log_exporters
from agent_sdk.observability.event_retention import EventRetentionPolicy
from agent_sdk.observability.audit_logs import AuditLogEntry, create_audit_loggers
from agent_sdk.observability.redaction import RedactionPolicy, Redactor
from agent_sdk.observability.otel import ObservabilityManager
from agent_sdk.observability.prometheus import ObservabilityPrometheusCollector
from prometheus_client import CollectorRegistry, CONTENT_TYPE_LATEST, generate_latest
from agent_sdk.core.streaming import TokenCounter
from agent_sdk.core.retry import RetryConfig, retry_with_backoff
from agent_sdk.execution.queue import ExecutionQueue
from agent_sdk.execution.durable_queue import DurableExecutionQueue, SQLiteQueueBackend, RedisQueueBackend
from agent_sdk.policies.prompt_registry import PromptPolicyRegistry
from agent_sdk.server.idempotency import IdempotencyStore
from agent_sdk.server.run_store import RunEventStore
from agent_sdk.storage import SQLiteStorage, PostgresStorage
from agent_sdk.server.gateway import GatewayServer
from agent_sdk.server.device_registry import DeviceRegistry
from agent_sdk.server.multi_tenant import MultiTenantStore, QuotaLimits, RetentionPolicyConfig
from agent_sdk.storage.control_plane import SQLiteControlPlane, PostgresControlPlane
from agent_sdk.server.channels import handle_web_channel
from agent_sdk.server.admin_ui import ADMIN_HTML
from agent_sdk.server.scheduler import Scheduler

logger = logging.getLogger(__name__)

def _hinted_detail(message: str, hint: str) -> str:
    return f"{message} Hint: {hint}"


def create_app(config_path: str = "config.yaml", storage_path: Optional[str] = None):
    """Create and configure FastAPI application
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        Configured FastAPI application
    """
    try:
        loader = PluginLoader()
        loader.load()
        planner, executor = load_config(config_path, MockLLMClient())
        runtime = PlannerExecutorRuntime(planner, executor)
        tracing_enabled = os.getenv("AGENT_SDK_TRACING_ENABLED", "").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        observability = ObservabilityManager(service_name="agent-sdk") if tracing_enabled else None
        if observability:
            planner.context.config["observability"] = observability
            executor.context.config["observability"] = observability
        prometheus_enabled = os.getenv("AGENT_SDK_PROMETHEUS_ENABLED", "").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        prometheus_registry = None
        if prometheus_enabled:
            prometheus_registry = CollectorRegistry()
            prometheus_registry.register(ObservabilityPrometheusCollector(observability))
        log_path = os.getenv("AGENT_SDK_RUN_LOG_PATH")
        log_stdout = os.getenv("AGENT_SDK_RUN_LOG_STDOUT", "").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        audit_path = os.getenv("AGENT_SDK_AUDIT_LOG_PATH")
        audit_stdout = os.getenv("AGENT_SDK_AUDIT_LOG_STDOUT", "").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        storage_backend = os.getenv("AGENT_SDK_STORAGE_BACKEND", "sqlite").lower()
        if storage_backend == "postgres":
            dsn = os.getenv("AGENT_SDK_POSTGRES_DSN")
            if not dsn:
                raise ConfigError("AGENT_SDK_POSTGRES_DSN is required for postgres storage")
            if PostgresStorage is None:
                raise ConfigError("psycopg is required for postgres storage")
            storage = PostgresStorage(dsn)
        else:
            db_path = storage_path or os.getenv("AGENT_SDK_DB_PATH", "agent_sdk.db")
            storage = SQLiteStorage(db_path)
        retention_policy = EventRetentionPolicy.from_env()
        redaction_policy = RedactionPolicy.from_env()
        redactor = Redactor(redaction_policy)
        stream_queue_size = int(os.getenv("AGENT_SDK_STREAM_QUEUE_SIZE", "200"))
        stream_max_events = int(os.getenv("AGENT_SDK_STREAM_MAX_EVENTS", "1000"))
        control_plane_backend = os.getenv("AGENT_SDK_CONTROL_PLANE_BACKEND", "memory").lower()
        control_plane = None
        if control_plane_backend == "postgres":
            dsn = os.getenv("AGENT_SDK_CONTROL_PLANE_DSN") or os.getenv("AGENT_SDK_POSTGRES_DSN")
            if not dsn:
                raise ConfigError("AGENT_SDK_CONTROL_PLANE_DSN is required for postgres control plane")
            control_plane = PostgresControlPlane(dsn)
        elif control_plane_backend == "sqlite":
            cp_path = os.getenv("AGENT_SDK_CONTROL_PLANE_DB_PATH", "control_plane.db")
            control_plane = SQLiteControlPlane(cp_path)
        tenant_store = MultiTenantStore(control_plane)
        try:
            tenant_store.set_model_catalog(load_model_names(config_path))
        except Exception:
            pass
        run_store = RunEventStore(
            max_events=stream_max_events,
            queue_size=stream_queue_size,
            exporters=create_run_log_exporters(
                path=log_path,
                emit_stdout=log_stdout,
            ),
            storage=storage if storage_backend == "postgres" else None,
            retention_policy=retention_policy,
            redactor=redactor,
            tenant_store=tenant_store,
        )
        prompt_registry = PromptPolicyRegistry()
        execution_mode = os.getenv("AGENT_SDK_EXECUTION_MODE", "direct").lower()
        queue_backend = os.getenv("AGENT_SDK_QUEUE_BACKEND", "memory").lower()
        durable_queue = None
        execution_queue = None
        if execution_mode == "queue":
            if queue_backend == "sqlite":
                queue_path = os.getenv("AGENT_SDK_QUEUE_DB_PATH", "queue.db")
                durable_queue = DurableExecutionQueue(
                    backend=SQLiteQueueBackend(queue_path),
                    handler=lambda payload: runtime.run_async(
                        payload["task"],
                        session_id=payload["session_id"],
                        run_id=payload["run_id"],
                    ),
                    poll_interval=float(os.getenv("AGENT_SDK_QUEUE_POLL_INTERVAL", "0.2")),
                    max_attempts=int(os.getenv("AGENT_SDK_QUEUE_MAX_ATTEMPTS", "3")),
                )
            elif queue_backend == "redis":
                redis_url = os.getenv("AGENT_SDK_REDIS_URL", "redis://localhost:6379/0")
                durable_queue = DurableExecutionQueue(
                    backend=RedisQueueBackend(redis_url),
                    handler=lambda payload: runtime.run_async(
                        payload["task"],
                        session_id=payload["session_id"],
                        run_id=payload["run_id"],
                    ),
                    poll_interval=float(os.getenv("AGENT_SDK_QUEUE_POLL_INTERVAL", "0.2")),
                    max_attempts=int(os.getenv("AGENT_SDK_QUEUE_MAX_ATTEMPTS", "3")),
                )
            else:
                execution_queue = ExecutionQueue(worker_count=int(os.getenv("AGENT_SDK_WORKER_COUNT", "2")))
        retry_config = RetryConfig(
            max_retries=int(os.getenv("AGENT_SDK_RETRY_MAX", "1")),
            base_delay=float(os.getenv("AGENT_SDK_RETRY_BASE_DELAY", "0.5")),
            max_delay=float(os.getenv("AGENT_SDK_RETRY_MAX_DELAY", "5.0")),
            exponential_base=float(os.getenv("AGENT_SDK_RETRY_EXP_BASE", "2.0")),
        )
        idempotency_store = IdempotencyStore(
            ttl_minutes=int(os.getenv("AGENT_SDK_IDEMPOTENCY_TTL_MINUTES", "60"))
        )
        audit_logger = create_audit_loggers(
            path=audit_path,
            emit_stdout=audit_stdout,
            redactor=redactor,
        )
        api_key_manager = get_api_key_manager()
        if api_key_manager.api_key:
            tenant_store.register_api_key(
                "default",
                api_key_manager.api_key,
                "env",
                role=os.getenv("API_KEY_ROLE", "admin"),
                scopes=[s.strip() for s in os.getenv("API_KEY_SCOPES", "").split(",") if s.strip()],
                expires_at=os.getenv("API_KEY_EXPIRES_AT"),
            )
            audit_logger.emit(
                AuditLogEntry(
                    action="api_key.registered",
                    actor="system",
                    org_id="default",
                    target_type="api_key",
                    metadata={"source": "env"},
                )
            )
        recovery_enabled = os.getenv("AGENT_SDK_RUN_RECOVERY_ENABLED", "true").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        if recovery_enabled:
            recovered = storage.recover_in_flight_runs()
            if recovered:
                logger.warning("Recovered %s in-flight runs after restart", recovered)

        device_registry = DeviceRegistry()
        logger.info("Application initialized successfully")
    except ConfigError as e:
        logger.error(f"Failed to initialize application: {e}")
        error_message = str(e)
        # Create a minimal app that reports the error
        app = FastAPI(title="Agent SDK", version="0.1.0")
        
        @app.get("/health")
        async def health_error():
            return {"status": "unhealthy", "error": error_message}

        @app.get("/ready")
        async def readiness_error():
            raise HTTPException(status_code=503, detail=f"Service not ready: {error_message}")
        
        return app

    app = FastAPI(
        title="Agent SDK",
        version="0.1.0",
        description="Agent SDK - Modular Agent Framework with Planning, Execution, and Observability"
    )
    app.state.observability = observability
    app.state.prometheus_enabled = prometheus_enabled
    app.state.prometheus_registry = prometheus_registry

    ui_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ui"))
    ui_source = os.path.join(ui_root, "index.html")
    ui_dist = os.path.join(ui_root, "dist", "index.html")

    def _resolve_ui_path() -> str:
        if os.path.exists(ui_dist):
            return ui_dist
        return ui_source

    def _org_id_from_request(request: Request) -> str:
        return request.headers.get("X-Org-Id", "default")

    def _audit_actor(request: Request) -> tuple[str, str]:
        api_key = request.headers.get("X-API-Key", "")
        info = get_api_key_manager().get_key_info(api_key)
        if info:
            return info.key, info.org_id
        return "unknown", "default"

    async def _run_with_policies(task: str, session_id: str, run_id: str):
        async def _invoke():
            return await runtime.run_async(task, session_id=session_id, run_id=run_id)

        async def _invoke_with_retry():
            if retry_config.max_retries <= 1:
                return await _invoke()
            return await retry_with_backoff(
                _invoke,
                max_retries=retry_config.max_retries,
                base_delay=retry_config.base_delay,
                max_delay=retry_config.max_delay,
                exponential_base=retry_config.exponential_base,
            )

        if durable_queue is not None:
            return await durable_queue.submit(
                {"task": task, "session_id": session_id, "run_id": run_id}
            )
        if execution_queue is not None:
            return await execution_queue.submit(_invoke_with_retry)
        return await _invoke_with_retry()

    async def _submit_scheduled(entry):
        org_id = entry.org_id
        allowed, reason = tenant_store.check_quota(org_id, new_session=True, new_run=True)
        if not allowed:
            logger.warning("Scheduled run blocked for org %s: %s", org_id, reason)
            return
        session_id = new_session_id()
        run_id = new_run_id()
        session = SessionMetadata(session_id=session_id, org_id=org_id)
        storage.create_session(session)
        tenant_store.record_session(org_id)
        requested_model = planner.context.model_config.model_id if planner.context.model_config else None
        resolved_model = tenant_store.resolve_model(org_id, requested_model)
        run_meta = RunMetadata(
            run_id=run_id,
            session_id=session_id,
            agent_id="planner-executor",
            org_id=org_id,
            status=RunStatus.RUNNING,
            model=resolved_model,
            metadata={"scheduled": True, "schedule_id": entry.schedule_id},
        )
        storage.create_run(run_meta)
        tenant_store.record_run(org_id)
        try:
            msgs = await _run_with_policies(entry.task, session_id=session_id, run_id=run_id)
            run_meta = RunMetadata(
                run_id=run_id,
                session_id=session_id,
                agent_id="planner-executor",
                org_id=org_id,
                status=RunStatus.COMPLETED,
                model=resolved_model,
                metadata={"scheduled": True, "schedule_id": entry.schedule_id},
            )
            storage.update_run(run_meta)
            token_count = sum(TokenCounter.count_tokens(m.content) for m in msgs)
            tenant_store.record_tokens(org_id, token_count)
        except Exception as exc:
            logger.error("Scheduled run failed: %s", exc, exc_info=True)
            run_meta = RunMetadata(
                run_id=run_id,
                session_id=session_id,
                agent_id="planner-executor",
                org_id=org_id,
                status=RunStatus.ERROR,
                model=resolved_model,
                metadata={"scheduled": True, "schedule_id": entry.schedule_id, "error": str(exc)},
            )
            storage.update_run(run_meta)

    scheduler = Scheduler(
        _submit_scheduled,
        poll_interval=float(os.getenv("AGENT_SDK_SCHEDULER_POLL_INTERVAL", "1.0")),
    )
    app.state.scheduler = scheduler

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure properly in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Basic API key auth middleware for protected routes
    protected_prefixes = ("/run", "/sessions", "/tools")
    public_paths = ("/health", "/ready", "/metrics", "/docs", "/openapi.json", "/redoc")

    @app.middleware("http")
    async def api_versioning_middleware(request: Request, call_next):
        original_path = request.scope.get("path", "")
        versioned = False
        if original_path == "/v1":
            request.scope["path"] = "/"
            versioned = True
        elif original_path.startswith("/v1/"):
            request.scope["path"] = original_path[3:]
            versioned = True
        response = await call_next(request)
        response.headers["X-API-Version"] = "v1"
        if not versioned and not original_path.startswith(public_paths):
            response.headers["X-API-Deprecated"] = "Use /v1 prefix for API requests"
        return response

    @app.middleware("http")
    async def api_key_middleware(request: Request, call_next):
        path = request.url.path
        if path.startswith(protected_prefixes) and path not in public_paths:
            api_key = request.headers.get("X-API-Key")
            if not api_key:
                return JSONResponse(
                    status_code=401,
                    content={
                        "detail": "Missing API key in X-API-Key header",
                        "hint": "Set API_KEY env var or pass X-API-Key header.",
                    },
                )
            manager = get_api_key_manager()
            if not manager.verify_key(api_key):
                return JSONResponse(
                    status_code=401,
                    content={
                        "detail": "Invalid API key",
                        "hint": "Ensure X-API-Key matches the API_KEY env var.",
                    },
                )
        return await call_next(request)

    @app.get("/", tags=["UI"])
    async def dev_console_root():
        ui_path = _resolve_ui_path()
        if not os.path.exists(ui_path):
            raise HTTPException(status_code=404, detail="UI not found")
        return FileResponse(ui_path, media_type="text/html")

    @app.get("/ui", tags=["UI"])
    async def dev_console():
        ui_path = _resolve_ui_path()
        if not os.path.exists(ui_path):
            raise HTTPException(status_code=404, detail="UI not found")
        return FileResponse(ui_path, media_type="text/html")

    @app.get("/admin", tags=["Admin"])
    async def admin_console():
        return HTMLResponse(ADMIN_HTML)

    @app.websocket("/ws")
    async def gateway_ws(websocket: WebSocket):
        await gateway.handle_connection(websocket)
    app.state.run_store = run_store
    app.state.storage = storage
    app.state.event_storage = storage if storage_backend == "postgres" else None
    app.state.tenant_store = tenant_store
    app.state.device_registry = device_registry
    app.state.audit_logger = audit_logger
    app.state.prompt_registry = prompt_registry
    app.state.execution_queue = execution_queue
    app.state.durable_queue = durable_queue
    app.state.retry_config = retry_config
    app.state.idempotency_store = idempotency_store

    @app.on_event("startup")
    async def _start_workers():
        if durable_queue is not None:
            await durable_queue.start()
        await scheduler.start()

    @app.on_event("shutdown")
    async def _stop_workers():
        if durable_queue is not None:
            await durable_queue.stop()
        await scheduler.stop()
    gateway = GatewayServer(
        runtime=runtime,
        run_store=run_store,
        storage=storage,
        api_key_manager=get_api_key_manager(),
        send_queue_size=int(os.getenv("AGENT_SDK_GATEWAY_QUEUE", "100")),
        tenant_store=tenant_store,
    )
    app.state.gateway = gateway

    # Health Check Endpoint
    @app.get("/health", response_model=HealthResponse, tags=["Health"])
    async def health():
        """Health check endpoint - returns 200 if service is running"""
        return {"status": "healthy", "version": "0.1.0"}

    # Readiness Check Endpoint
    @app.get("/ready", response_model=ReadyResponse, tags=["Health"])
    async def readiness():
        """Readiness check endpoint - returns 200 if service is ready to accept requests"""
        try:
            # Verify configuration is loaded and valid
            if not planner or not executor:
                raise Exception("Agents not initialized")
            
            logger.debug("Readiness check passed")
            return {"ready": True}
        except Exception as e:
            logger.error(f"Readiness check failed: {e}")
            raise HTTPException(
                status_code=503,
                detail=_hinted_detail(
                    f"Service not ready: {str(e)}",
                    "Verify config.yaml and plugin initialization.",
                ),
            )

    @app.get("/metrics", include_in_schema=False)
    async def metrics_endpoint():
        """Prometheus metrics endpoint."""
        if not app.state.prometheus_enabled or app.state.prometheus_registry is None:
            raise HTTPException(status_code=404, detail="Prometheus metrics disabled")
        payload = generate_latest(app.state.prometheus_registry)
        return Response(content=payload, media_type=CONTENT_TYPE_LATEST)

    # Task Execution Endpoint
    @app.post(
        "/run",
        response_model=TaskResponse,
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_RUN_WRITE]))],
        tags=["Tasks"]
    )
    async def run_task(req: RunTaskRequest, request: Request):
        """Execute a task using the planner-executor runtime
        
        Args:
            req: Task execution request with task description and optional config
            
        Returns:
            Task execution result with status and messages
        """
        try:
            logger.info(f"Executing task: {req.task[:100]}")
            org_id = _org_id_from_request(request)
            idempotency_key = request.headers.get("Idempotency-Key")
            if idempotency_key:
                cached = idempotency_store.get(idempotency_key)
                if cached:
                    return TaskResponse(**cached)

            allowed, reason = tenant_store.check_quota(org_id, new_session=True, new_run=True)
            if not allowed:
                raise HTTPException(status_code=429, detail=f"Quota exceeded: {reason}")

            session_id = new_session_id()
            run_id = new_run_id()

            session = SessionMetadata(session_id=session_id, org_id=org_id)
            storage.create_session(session)
            tenant_store.record_session(org_id)

            requested_model = planner.context.model_config.model_id if planner.context.model_config else None
            resolved_model = tenant_store.resolve_model(org_id, requested_model)
            run_meta = RunMetadata(
                run_id=run_id,
                session_id=session_id,
                agent_id="planner-executor",
                org_id=org_id,
                status=RunStatus.RUNNING,
                model=resolved_model,
            )
            storage.create_run(run_meta)
            tenant_store.record_run(org_id)

            msgs = await _run_with_policies(req.task, session_id=session_id, run_id=run_id)
            run_meta = RunMetadata(
                run_id=run_id,
                session_id=session_id,
                agent_id="planner-executor",
                org_id=org_id,
                status=RunStatus.COMPLETED,
                model=resolved_model,
            )
            storage.update_run(run_meta)
            
            token_count = sum(TokenCounter.count_tokens(m.content) for m in msgs)
            tenant_store.record_tokens(org_id, token_count)
            result_data = {
                "run_id": run_id,
                "session_id": session_id,
                "messages": [
                    {
                        "id": m.id,
                        "role": m.role,
                        "content": m.content,
                        "metadata": m.metadata
                    }
                    for m in msgs
                ]
            }
            
            logger.info(f"Task completed successfully with {len(msgs)} messages")
            response = TaskResponse(
                status="success",
                result=result_data,
                execution_time_ms=0
            )
            if idempotency_key:
                idempotency_store.set(idempotency_key, response.model_dump())
            return response
        except ValidationError as e:
            logger.warning(f"Validation error: {e}")
            raise HTTPException(
                status_code=400,
                detail=_hinted_detail(
                    f"Invalid input: {str(e)}",
                    "Check required fields and types in the request payload.",
                ),
            )
        except HTTPException:
            raise
        except AgentSDKException as e:
            logger.error(f"Agent SDK error: {e}")
            raise HTTPException(
                status_code=500,
                detail=_hinted_detail(
                    f"Task execution failed: {str(e)}",
                    "Review logs for stack trace and configuration issues.",
                ),
            )
        except Exception as e:
            logger.error(f"Unexpected error during task execution: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=_hinted_detail(
                    "Internal server error",
                    "Check server logs for details.",
                ),
            )

    # Streaming Task Execution Endpoint
    @app.post(
        "/run/stream",
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_RUN_WRITE]))],
        tags=["Tasks"]
    )
    async def run_task_stream(req: RunTaskRequest, request: Request):
        """Execute a task and stream events in real-time
        
        Args:
            req: Task execution request
            
        Returns:
            Server-Sent Events stream with execution events
        """
        async def emit_run_events(run_id: str, session_id: str, org_id: str, model_id: Optional[str]) -> None:
            seq = 0
            try:
                start_event = StreamEnvelope(
                    run_id=run_id,
                    session_id=session_id,
                    stream=StreamChannel.LIFECYCLE,
                    event="start",
                    payload={"task": req.task},
                    status=RunStatus.RUNNING.value,
                    seq=seq,
                    metadata={"org_id": org_id},
                )
                run_store.append_event(run_id, start_event)
                seq += 1

                msgs = await _run_with_policies(req.task, session_id=session_id, run_id=run_id)
                for msg in msgs:
                    run_store.append_event(
                        run_id,
                        StreamEnvelope(
                            run_id=run_id,
                            session_id=session_id,
                            stream=StreamChannel.ASSISTANT,
                            event="message",
                            payload={
                                "id": msg.id,
                                "role": msg.role,
                                "content": msg.content,
                                "metadata": msg.metadata,
                            },
                            seq=seq,
                            metadata={"org_id": org_id},
                        ),
                    )
                    seq += 1

                end_event = StreamEnvelope(
                    run_id=run_id,
                    session_id=session_id,
                    stream=StreamChannel.LIFECYCLE,
                    event="end",
                    payload={"status": "completed"},
                    status=RunStatus.COMPLETED.value,
                    seq=seq,
                    metadata={"org_id": org_id},
                )
                run_store.append_event(run_id, end_event)
                storage.update_run(
                    RunMetadata(
                        run_id=run_id,
                        session_id=session_id,
                        agent_id="planner-executor",
                        status=RunStatus.COMPLETED,
                        model=model_id,
                    )
                )
                token_count = sum(TokenCounter.count_tokens(m.content) for m in msgs)
                tenant_store.record_tokens(org_id, token_count)
            except Exception as e:
                logger.error(f"Error during streaming execution: {e}", exc_info=True)
                run_store.append_event(
                    run_id,
                    StreamEnvelope(
                        run_id=run_id,
                        session_id=session_id,
                        stream=StreamChannel.LIFECYCLE,
                        event="error",
                        payload={"error": str(e)},
                        status=RunStatus.ERROR.value,
                        seq=seq,
                        metadata={"org_id": org_id},
                    ),
                )
                storage.update_run(
                    RunMetadata(
                        run_id=run_id,
                        session_id=session_id,
                        agent_id="planner-executor",
                        status=RunStatus.ERROR,
                        model=model_id,
                    )
                )

        async def event_generator(run_id: str):
            try:
                async for event in run_store.stream(run_id):
                    yield event.to_sse()
            except Exception as e:
                logger.error(f"Error during streaming event streaming: {e}", exc_info=True)
                yield StreamEnvelope(
                    run_id=run_id,
                    session_id="unknown",
                    stream=StreamChannel.LIFECYCLE,
                    event="error",
                    payload={"error": str(e)},
                    status=RunStatus.ERROR.value,
                ).to_sse()

        org_id = _org_id_from_request(request)
        allowed, reason = tenant_store.check_quota(org_id, new_session=True, new_run=True)
        if not allowed:
            raise HTTPException(status_code=429, detail=f"Quota exceeded: {reason}")
        run_id = new_run_id()
        session_id = new_session_id()
        storage.create_session(SessionMetadata(session_id=session_id, org_id=org_id))
        tenant_store.record_session(org_id)
        requested_model = planner.context.model_config.model_id if planner.context.model_config else None
        resolved_model = tenant_store.resolve_model(org_id, requested_model)
        storage.create_run(
            RunMetadata(
                run_id=run_id,
                session_id=session_id,
                agent_id="planner-executor",
                org_id=org_id,
                status=RunStatus.RUNNING,
                model=resolved_model,
            )
        )
        tenant_store.record_run(org_id)
        run_store.create_run(run_id)
        asyncio.create_task(emit_run_events(run_id, session_id, org_id, resolved_model))

        return StreamingResponse(
            event_generator(run_id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            }
        )

    @app.get(
        "/run/{run_id}/events",
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_RUN_READ]))],
        tags=["Tasks"]
    )
    async def stream_run_events(run_id: str, request: Request):
        """Stream events for a given run id."""
        if not run_store.has_run(run_id):
            if app.state.event_storage is None:
                raise HTTPException(status_code=404, detail="Run not found")
        run = storage.get_run(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        if run.org_id != _org_id_from_request(request):
            raise HTTPException(status_code=403, detail="Forbidden")

        async def event_generator():
            if run_store.has_run(run_id):
                async for event in run_store.stream(run_id):
                    yield event.to_sse()
                return
            events = app.state.event_storage.list_events(run_id)  # type: ignore[union-attr]
            for event in events:
                yield event.to_sse()

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            }
        )

    @app.get(
        "/run/{run_id}/events/replay",
        response_model=ReplayEventsResponse,
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_RUN_READ]))],
        tags=["Tasks"],
    )
    async def replay_run_events(run_id: str, request: Request, from_seq: Optional[int] = None, limit: int = 1000):
        run = storage.get_run(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        if run.org_id != _org_id_from_request(request):
            raise HTTPException(status_code=403, detail="Forbidden")
        if app.state.event_storage is None:
            events = run_store.list_events_from(run_id, from_seq)
        else:
            events = app.state.event_storage.list_events_from(run_id, from_seq, limit=limit)
        payload = [event.to_dict() for event in events[:limit]]
        return ReplayEventsResponse(events=payload, count=len(payload))

    @app.get(
        "/run/{run_id}",
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_RUN_READ]))],
        tags=["Tasks"]
    )
    async def get_run(run_id: str, request: Request):
        run = storage.get_run(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        if run.org_id != _org_id_from_request(request):
            raise HTTPException(status_code=403, detail="Forbidden")
        data = asdict(run)
        data["status"] = run.status.value
        return data

    @app.get(
        "/sessions",
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_SESSION_READ]))],
        tags=["Tasks"]
    )
    async def list_sessions(request: Request, limit: int = 100):
        sessions = storage.list_sessions(limit=limit)
        org_id = _org_id_from_request(request)
        return [asdict(session) for session in sessions if session.org_id == org_id]

    @app.get(
        "/sessions/{session_id}",
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_SESSION_READ]))],
        tags=["Tasks"]
    )
    async def get_session(session_id: str, request: Request):
        session = storage.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        if session.org_id != _org_id_from_request(request):
            raise HTTPException(status_code=403, detail="Forbidden")
        return asdict(session)

    @app.post(
        "/channels/webhook",
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_CHANNEL_WRITE]))],
        tags=["Channels"],
    )
    async def channel_webhook(req: ChannelMessageRequest, request: Request):
        if req.channel != "web":
            raise HTTPException(status_code=400, detail="Unsupported channel")
        org_id = _org_id_from_request(request)
        if req.session_id is None or storage.get_session(req.session_id) is None:
            tenant_store.record_session(org_id)
        tenant_store.record_run(org_id)
        return await handle_web_channel(
            runtime=runtime,
            storage=storage,
            run_store=run_store,
            message=req.message,
            session_id=req.session_id,
            org_id=org_id,
        )

    @app.post(
        "/devices/register",
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_DEVICE_MANAGE]))],
        tags=["Devices"],
    )
    async def register_device(req: DeviceRegisterRequest):
        record = device_registry.register_device(req.name)
        return {
            "device_id": record.device_id,
            "pairing_code": record.pairing_code,
            "created_at": record.created_at,
        }

    @app.post(
        "/devices/pair",
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_DEVICE_MANAGE]))],
        tags=["Devices"],
    )
    async def pair_device(req: DevicePairRequest):
        paired = device_registry.pair_device(req.device_id, req.pairing_code, req.agent_id)
        if not paired:
            raise HTTPException(status_code=400, detail="Invalid device or pairing code")
        return {"status": "paired", "device_id": req.device_id, "agent_id": req.agent_id}

    @app.get(
        "/admin/orgs",
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_ADMIN]))],
        tags=["Admin"],
    )
    async def list_orgs(request: Request):
        actor, org_id = _audit_actor(request)
        audit_logger.emit(
            AuditLogEntry(
                action="admin.orgs.list",
                actor=actor,
                org_id=org_id,
                target_type="organization",
            )
        )
        return [asdict(org) for org in tenant_store.list_orgs()]

    @app.get(
        "/admin/api-keys",
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_ADMIN]))],
        tags=["Admin"],
    )
    async def list_api_keys(request: Request, org_id: Optional[str] = None):
        actor, audit_org = _audit_actor(request)
        audit_logger.emit(
            AuditLogEntry(
                action="admin.api_keys.list",
                actor=actor,
                org_id=audit_org,
                target_type="api_key",
                metadata={"filter_org_id": org_id} if org_id else {},
            )
        )
        return [asdict(record) for record in tenant_store.list_api_keys(org_id)]

    @app.post(
        "/admin/api-keys",
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_ADMIN]))],
        tags=["Admin"],
    )
    async def create_api_key(req: APIKeyCreateRequest, request: Request):
        record = tenant_store.create_api_key(
            req.org_id,
            req.label,
            role=req.role,
            scopes=req.scopes,
            expires_at=req.expires_at,
            rate_limit_per_minute=req.rate_limit_per_minute,
            ip_allowlist=req.ip_allowlist,
        )
        get_api_key_manager().add_key(
            record.key,
            role=req.role,
            scopes=req.scopes,
            org_id=req.org_id,
            expires_at=req.expires_at,
            rate_limit_per_minute=req.rate_limit_per_minute,
            ip_allowlist=req.ip_allowlist,
        )
        actor, _ = _audit_actor(request)
        audit_logger.emit(
            AuditLogEntry(
                action="api_key.created",
                actor=actor,
                org_id=req.org_id,
                target_type="api_key",
                target_id=record.key_id,
                metadata={"label": req.label, "role": req.role, "scopes": req.scopes},
            )
        )
        return asdict(record)

    @app.post(
        "/admin/api-keys/{key_id}/rotate",
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_ADMIN]))],
        tags=["Admin"],
    )
    async def rotate_api_key(key_id: str, request: Request):
        rotated = tenant_store.rotate_api_key(key_id)
        if not rotated:
            raise HTTPException(status_code=404, detail="API key not found")
        record, old_record = rotated
        manager = get_api_key_manager()
        manager.remove_key(old_record.key)
        manager.add_key(
            record.key,
            role=record.role,
            scopes=record.scopes,
            org_id=record.org_id,
            expires_at=record.expires_at,
        )
        actor, _ = _audit_actor(request)
        audit_logger.emit(
            AuditLogEntry(
                action="api_key.rotated",
                actor=actor,
                org_id=record.org_id,
                target_type="api_key",
                target_id=record.key_id,
            )
        )
        return asdict(record)

    @app.get(
        "/admin/usage",
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_ADMIN]))],
        tags=["Admin"],
    )
    async def usage_summary(request: Request, org_id: Optional[str] = None):
        actor, audit_org = _audit_actor(request)
        audit_logger.emit(
            AuditLogEntry(
                action="admin.usage.list",
                actor=actor,
                org_id=audit_org,
                target_type="usage",
                metadata={"filter_org_id": org_id} if org_id else {},
            )
        )
        return [asdict(summary) for summary in tenant_store.usage_summary(org_id)]

    @app.get(
        "/admin/quotas",
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_ADMIN]))],
        tags=["Admin"],
    )
    async def get_quota(request: Request, org_id: Optional[str] = None):
        actor, audit_org = _audit_actor(request)
        audit_logger.emit(
            AuditLogEntry(
                action="admin.quotas.get",
                actor=actor,
                org_id=audit_org,
                target_type="quota",
                metadata={"filter_org_id": org_id} if org_id else {},
            )
        )
        if org_id:
            quota = tenant_store.get_quota(org_id)
            return {"org_id": org_id, **quota.__dict__}
        return [
            {"org_id": org.org_id, **tenant_store.get_quota(org.org_id).__dict__}
            for org in tenant_store.list_orgs()
        ]

    @app.post(
        "/admin/quotas",
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_ADMIN]))],
        tags=["Admin"],
    )
    async def set_quota(req: QuotaUpdateRequest, request: Request):
        tenant_store.set_quota(
            req.org_id,
            QuotaLimits(
                max_runs=req.max_runs,
                max_sessions=req.max_sessions,
                max_tokens=req.max_tokens,
            ),
        )
        actor, audit_org = _audit_actor(request)
        audit_logger.emit(
            AuditLogEntry(
                action="admin.quotas.set",
                actor=actor,
                org_id=audit_org,
                target_type="quota",
                metadata=req.model_dump(),
            )
        )
        quota = tenant_store.get_quota(req.org_id)
        return {"org_id": req.org_id, **quota.__dict__}

    @app.get(
        "/admin/retention",
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_ADMIN]))],
        tags=["Admin"],
    )
    async def get_retention_policy(request: Request, org_id: Optional[str] = None):
        actor, audit_org = _audit_actor(request)
        audit_logger.emit(
            AuditLogEntry(
                action="admin.retention.get",
                actor=actor,
                org_id=audit_org,
                target_type="retention",
                metadata={"filter_org_id": org_id} if org_id else {},
            )
        )
        if org_id:
            policy = tenant_store.get_retention_policy(org_id)
            return {"org_id": org_id, "max_events": policy.max_events}
        return [
            {"org_id": org.org_id, "max_events": tenant_store.get_retention_policy(org.org_id).max_events}
            for org in tenant_store.list_orgs()
        ]

    @app.post(
        "/admin/retention",
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_ADMIN]))],
        tags=["Admin"],
    )
    async def set_retention_policy(req: RetentionPolicyRequest, request: Request):
        tenant_store.set_retention_policy(
            req.org_id,
            RetentionPolicyConfig(max_events=req.max_events),
        )
        actor, audit_org = _audit_actor(request)
        audit_logger.emit(
            AuditLogEntry(
                action="admin.retention.set",
                actor=actor,
                org_id=audit_org,
                target_type="retention",
                metadata=req.model_dump(),
            )
        )
        policy = tenant_store.get_retention_policy(req.org_id)
        return {"org_id": req.org_id, "max_events": policy.max_events}

    @app.get(
        "/admin/schedules",
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_ADMIN]))],
        tags=["Admin"],
    )
    async def list_schedules(request: Request, org_id: Optional[str] = None):
        actor, audit_org = _audit_actor(request)
        audit_logger.emit(
            AuditLogEntry(
                action="admin.schedules.list",
                actor=actor,
                org_id=audit_org,
                target_type="schedule",
                metadata={"filter_org_id": org_id} if org_id else {},
            )
        )
        return [asdict(entry) for entry in scheduler.list_schedules(org_id)]

    @app.post(
        "/admin/schedules",
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_ADMIN]))],
        tags=["Admin"],
    )
    async def create_schedule(req: ScheduleCreateRequest, request: Request):
        entry = scheduler.add_schedule(
            org_id=req.org_id,
            task=req.task,
            cron=req.cron,
            enabled=req.enabled,
        )
        actor, audit_org = _audit_actor(request)
        audit_logger.emit(
            AuditLogEntry(
                action="admin.schedules.create",
                actor=actor,
                org_id=audit_org,
                target_type="schedule",
                target_id=entry.schedule_id,
                metadata=asdict(entry),
            )
        )
        return asdict(entry)

    @app.delete(
        "/admin/schedules/{schedule_id}",
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_ADMIN]))],
        tags=["Admin"],
    )
    async def delete_schedule(schedule_id: str, request: Request):
        removed = scheduler.remove_schedule(schedule_id)
        actor, audit_org = _audit_actor(request)
        audit_logger.emit(
            AuditLogEntry(
                action="admin.schedules.delete",
                actor=actor,
                org_id=audit_org,
                target_type="schedule",
                target_id=schedule_id,
                metadata={"removed": removed},
            )
        )
        if not removed:
            raise HTTPException(status_code=404, detail="Schedule not found")
        return {"schedule_id": schedule_id, "removed": True}

    @app.get(
        "/admin/model-policies",
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_ADMIN]))],
        tags=["Admin"],
    )
    async def get_model_policy(request: Request, org_id: Optional[str] = None):
        actor, audit_org = _audit_actor(request)
        audit_logger.emit(
            AuditLogEntry(
                action="admin.model_policies.get",
                actor=actor,
                org_id=audit_org,
                target_type="model_policy",
                metadata={"filter_org_id": org_id} if org_id else {},
            )
        )
        if org_id:
            policy = tenant_store.get_model_policy(org_id)
            return {"org_id": org_id, "policy": policy.__dict__ if policy else None}
        return [
            {"org_id": org.org_id, "policy": tenant_store.get_model_policy(org.org_id).__dict__ if tenant_store.get_model_policy(org.org_id) else None}
            for org in tenant_store.list_orgs()
        ]

    @app.post(
        "/admin/model-policies",
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_ADMIN]))],
        tags=["Admin"],
    )
    async def set_model_policy(req: ModelPolicyRequest, request: Request):
        policy = tenant_store.set_model_policy(
            req.org_id,
            allowed_models=req.allowed_models,
            fallback_models=req.fallback_models or None,
        )
        actor, audit_org = _audit_actor(request)
        audit_logger.emit(
            AuditLogEntry(
                action="admin.model_policies.set",
                actor=actor,
                org_id=audit_org,
                target_type="model_policy",
                metadata=req.model_dump(),
            )
        )
        return {"org_id": req.org_id, "policy": policy.__dict__}

    @app.get(
        "/admin/policies",
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_ADMIN]))],
        tags=["Admin"],
    )
    async def list_policies(request: Request):
        actor, audit_org = _audit_actor(request)
        audit_logger.emit(
            AuditLogEntry(
                action="admin.policies.list",
                actor=actor,
                org_id=audit_org,
                target_type="policy",
            )
        )
        return {"policies": prompt_registry.list_policies()}

    @app.post(
        "/admin/policies",
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_ADMIN]))],
        tags=["Admin"],
    )
    async def create_policy(req: PromptPolicyCreateRequest, request: Request):
        version = prompt_registry.create_version(
            policy_id=req.policy_id,
            content=req.content,
            description=req.description,
        )
        actor, audit_org = _audit_actor(request)
        audit_logger.emit(
            AuditLogEntry(
                action="admin.policies.create",
                actor=actor,
                org_id=audit_org,
                target_type="policy",
                target_id=req.policy_id,
                metadata={"version": version.version},
            )
        )
        return version.__dict__

    @app.get(
        "/admin/policies/{policy_id}",
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_ADMIN]))],
        tags=["Admin"],
    )
    async def list_policy_versions(policy_id: str, request: Request):
        actor, audit_org = _audit_actor(request)
        audit_logger.emit(
            AuditLogEntry(
                action="admin.policies.versions",
                actor=actor,
                org_id=audit_org,
                target_type="policy",
                target_id=policy_id,
            )
        )
        versions = [version.__dict__ for version in prompt_registry.list_versions(policy_id)]
        return {"policy_id": policy_id, "versions": versions}

    @app.get(
        "/admin/policies/{policy_id}/latest",
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_ADMIN]))],
        tags=["Admin"],
    )
    async def get_latest_policy(policy_id: str, request: Request):
        actor, audit_org = _audit_actor(request)
        audit_logger.emit(
            AuditLogEntry(
                action="admin.policies.latest",
                actor=actor,
                org_id=audit_org,
                target_type="policy",
                target_id=policy_id,
            )
        )
        latest = prompt_registry.latest(policy_id)
        if not latest:
            raise HTTPException(status_code=404, detail="Policy not found")
        return latest.__dict__

    @app.post(
        "/admin/runs/{run_id}/events/purge",
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_ADMIN]))],
        tags=["Admin"],
    )
    async def purge_run_events(run_id: str, request: Request, body: RunEventsDeleteRequest):
        run = storage.get_run(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        if run.org_id != _org_id_from_request(request):
            raise HTTPException(status_code=403, detail="Forbidden")
        deleted = storage.delete_events(run_id, before_seq=body.before_seq)
        actor, org_id = _audit_actor(request)
        audit_logger.emit(
            AuditLogEntry(
                action="run.events.purged",
                actor=actor,
                org_id=org_id,
                target_type="run",
                target_id=run_id,
                metadata={"before_seq": body.before_seq, "deleted": deleted},
            )
        )
        return {"run_id": run_id, "deleted": deleted}

    @app.delete(
        "/admin/runs/{run_id}",
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_ADMIN]))],
        tags=["Admin"],
    )
    async def delete_run(run_id: str, request: Request):
        run = storage.get_run(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        if run.org_id != _org_id_from_request(request):
            raise HTTPException(status_code=403, detail="Forbidden")
        deleted = storage.delete_run(run_id)
        actor, org_id = _audit_actor(request)
        audit_logger.emit(
            AuditLogEntry(
                action="run.deleted",
                actor=actor,
                org_id=org_id,
                target_type="run",
                target_id=run_id,
                metadata={"deleted": deleted},
            )
        )
        return {"run_id": run_id, "deleted": bool(deleted)}

    @app.delete(
        "/admin/sessions/{session_id}",
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_ADMIN]))],
        tags=["Admin"],
    )
    async def delete_session(session_id: str, request: Request):
        session = storage.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        if session.org_id != _org_id_from_request(request):
            raise HTTPException(status_code=403, detail="Forbidden")
        deleted = storage.delete_session(session_id)
        actor, org_id = _audit_actor(request)
        audit_logger.emit(
            AuditLogEntry(
                action="session.deleted",
                actor=actor,
                org_id=org_id,
                target_type="session",
                target_id=session_id,
                metadata={"deleted": deleted},
            )
        )
        return {"session_id": session_id, "deleted": bool(deleted)}

    # List Tools Endpoint
    @app.get("/tools", tags=["Tools"], dependencies=[Depends(require_scopes([SCOPE_TOOLS_READ]))])
    async def list_tools(api_key: str = Depends(verify_api_key)):
        """List available tools
        
        Returns:
            List of available tools with descriptions
        """
        try:
            tools = []
            for name, tool in planner.context.tools.items():
                tools.append({
                    "name": name,
                    "description": tool.description
                })
            
            logger.debug(f"Returning {len(tools)} tools")
            return {
                "tools": tools,
                "count": len(tools)
            }
        except Exception as e:
            logger.error(f"Error listing tools: {e}")
            raise HTTPException(status_code=500, detail="Failed to list tools")

    return app
