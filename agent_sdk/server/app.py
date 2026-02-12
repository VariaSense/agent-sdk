import logging
import asyncio
import os
import csv
import io
import json
import hashlib
from datetime import datetime, timezone, timedelta
import secrets
from dataclasses import asdict
from typing import Optional, Dict, Any
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
    get_api_key_info,
    get_api_key_manager,
    require_scopes,
    APIKeyInfo,
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
    ProjectQuotaUpdateRequest,
    APIKeyQuotaUpdateRequest,
    RetentionPolicyRequest,
    PrivacyExportRequest,
    ScheduleCreateRequest,
    UserCreateRequest,
    ServiceAccountCreateRequest,
    AuthValidateRequest,
    ResidencyRequest,
    EncryptionKeyRequest,
    PromptPolicyCreateRequest,
    PolicyBundleCreateRequest,
    PolicyBundleAssignRequest,
    PolicyApprovalSubmitRequest,
    PolicyApprovalReviewRequest,
    PolicyPresetRequest,
    ProjectCreateRequest,
    WebhookSubscriptionRequest,
    SecretRotationRequest,
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
from agent_sdk.observability.audit_logs import AuditLogEntry, AuditHashChain, create_audit_loggers
from agent_sdk.observability.redaction import RedactionPolicy, Redactor
from agent_sdk.observability.otel import ObservabilityManager
from agent_sdk.observability.prometheus import ObservabilityPrometheusCollector
from prometheus_client import CollectorRegistry, CONTENT_TYPE_LATEST, generate_latest
from agent_sdk.core.streaming import TokenCounter
from agent_sdk.core.retry import RetryConfig, retry_with_backoff
from agent_sdk.privacy import PrivacyExporter
from agent_sdk.secrets_rotation import find_due_policies, emit_rotation_due
from agent_sdk.execution.queue import ExecutionQueue
from agent_sdk.execution.durable_queue import (
    DurableExecutionQueue,
    SQLiteQueueBackend,
    RedisQueueBackend,
    SQSQueueBackend,
    KafkaQueueBackend,
)
from agent_sdk.policy.engine import PolicyEngine, safety_preset, validate_policy_content
from agent_sdk.policy.types import PolicyApprovalStatus
from agent_sdk.policies.prompt_registry import PromptPolicyRegistry
from agent_sdk.server.idempotency import IdempotencyStore
from agent_sdk.server.run_store import RunEventStore
from agent_sdk.reliability.policy import ReliabilityManager, RetryPolicy, CircuitBreakerPolicy, ReplayStore
from agent_sdk.webhooks import WebhookDispatcher, WebhookSubscription, WebhookAuditExporter
from agent_sdk.archival import LocalArchiveBackend
from agent_sdk.llm.health import ProviderHealthMonitor
from agent_sdk.storage import SQLiteStorage, PostgresStorage
from agent_sdk.server.gateway import GatewayServer
from agent_sdk.server.device_registry import DeviceRegistry
from agent_sdk.server.multi_tenant import MultiTenantStore, QuotaLimits, RetentionPolicyConfig
from agent_sdk.storage.control_plane import SQLiteControlPlane, PostgresControlPlane
from agent_sdk.server.channels import handle_web_channel
from agent_sdk.server.admin_ui import ADMIN_HTML
from agent_sdk.server.scheduler import Scheduler, SQLiteSchedulerStore
from agent_sdk.identity.providers import (
    OIDCProvider,
    SAMLProvider,
    MockIdentityProvider,
    load_group_mapping,
)
from agent_sdk.encryption import generate_key
from agent_sdk.sandbox import LocalToolSandbox, DockerToolSandbox

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
        provider_health = ProviderHealthMonitor()
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
        sandbox_mode = os.getenv("AGENT_SDK_TOOL_SANDBOX", "").lower()
        sandbox_timeout = float(os.getenv("AGENT_SDK_TOOL_SANDBOX_TIMEOUT", "10"))
        sandbox = None
        if sandbox_mode == "local":
            sandbox = LocalToolSandbox(timeout_seconds=sandbox_timeout)
        elif sandbox_mode == "docker":
            sandbox = DockerToolSandbox()
        if sandbox:
            planner.context.config["tool_sandbox"] = sandbox
            executor.context.config["tool_sandbox"] = sandbox
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
        audit_hash_chain_enabled = os.getenv("AGENT_SDK_AUDIT_HASH_CHAIN", "").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        audit_http_endpoint = os.getenv("AGENT_SDK_AUDIT_HTTP_ENDPOINT")
        audit_http_timeout = float(os.getenv("AGENT_SDK_AUDIT_HTTP_TIMEOUT", "5.0"))
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
        archive_backend = LocalArchiveBackend(os.getenv("AGENT_SDK_ARCHIVE_PATH", "archives"))
        privacy_exporter = PrivacyExporter(os.getenv("AGENT_SDK_PRIVACY_EXPORT_PATH", "privacy_exports"))
        secret_rotation_enabled = os.getenv("AGENT_SDK_SECRET_ROTATION_AUTOMATION", "").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        secret_rotation_interval = float(os.getenv("AGENT_SDK_SECRET_ROTATION_INTERVAL_SECONDS", "3600"))
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
        policy_engine = PolicyEngine(tenant_store)
        policy_approval_required = os.getenv("AGENT_SDK_POLICY_APPROVAL_REQUIRED", "true").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        webhook_dispatcher = WebhookDispatcher(tenant_store.list_webhook_subscriptions())
        reliability_enabled = os.getenv("AGENT_SDK_RELIABILITY_ENABLED", "").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        reliability_manager = None
        if reliability_enabled:
            retry_policy = RetryPolicy(
                max_retries=int(os.getenv("AGENT_SDK_TOOL_RETRY_MAX", "2")),
                base_delay=float(os.getenv("AGENT_SDK_TOOL_RETRY_BASE_DELAY", "0.5")),
                max_delay=float(os.getenv("AGENT_SDK_TOOL_RETRY_MAX_DELAY", "5.0")),
                exponential_base=float(os.getenv("AGENT_SDK_TOOL_RETRY_EXP_BASE", "2.0")),
            )
            breaker_policy = CircuitBreakerPolicy(
                failure_threshold=int(os.getenv("AGENT_SDK_TOOL_CIRCUIT_FAILURE_THRESHOLD", "3")),
                reset_timeout_seconds=float(os.getenv("AGENT_SDK_TOOL_CIRCUIT_RESET_SECONDS", "30")),
            )
            reliability_manager = ReliabilityManager(retry_policy, breaker_policy)
        try:
            tenant_store.set_model_catalog(load_model_names(config_path))
        except Exception:
            pass
        encryption_enabled = os.getenv("AGENT_SDK_ENCRYPTION_ENABLED", "").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        if encryption_enabled:
            storage.set_encryption_resolver(lambda org_id: tenant_store.get_encryption_key(org_id))
        planner.context.config["policy_engine"] = policy_engine
        executor.context.config["policy_engine"] = policy_engine
        if reliability_manager:
            planner.context.config["reliability_manager"] = reliability_manager
            executor.context.config["reliability_manager"] = reliability_manager
        replay_mode = os.getenv("AGENT_SDK_REPLAY_MODE", "").lower() in {"1", "true", "yes", "on"}
        replay_store = None
        replay_path = os.getenv("AGENT_SDK_REPLAY_PATH")
        if replay_path and os.path.exists(replay_path):
            try:
                with open(replay_path, "r", encoding="utf-8") as handle:
                    replay_store = ReplayStore(json.load(handle))
            except Exception:
                replay_store = ReplayStore()
        elif replay_mode:
            replay_store = ReplayStore()
        if replay_store:
            executor.context.config["replay_store"] = replay_store
            executor.context.config["replay_mode"] = replay_mode
            executor.context.config["replay_strict"] = os.getenv("AGENT_SDK_REPLAY_STRICT", "").lower() in {"1", "true", "yes", "on"}
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
        idp_provider = os.getenv("AGENT_SDK_IDP_PROVIDER", "mock").lower()
        if idp_provider == "oidc":
            identity_provider = OIDCProvider()
        elif idp_provider == "saml":
            identity_provider = SAMLProvider()
        else:
            identity_provider = MockIdentityProvider()
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
                        org_id=payload.get("org_id"),
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
                        org_id=payload.get("org_id"),
                    ),
                    poll_interval=float(os.getenv("AGENT_SDK_QUEUE_POLL_INTERVAL", "0.2")),
                    max_attempts=int(os.getenv("AGENT_SDK_QUEUE_MAX_ATTEMPTS", "3")),
                )
            elif queue_backend == "sqs":
                queue_url = os.getenv("AGENT_SDK_SQS_QUEUE_URL")
                if not queue_url:
                    raise ConfigError("AGENT_SDK_SQS_QUEUE_URL is required for SQS backend")
                dlq_url = os.getenv("AGENT_SDK_SQS_DLQ_URL")
                durable_queue = DurableExecutionQueue(
                    backend=SQSQueueBackend(queue_url, dlq_url=dlq_url),
                    handler=lambda payload: runtime.run_async(
                        payload["task"],
                        session_id=payload["session_id"],
                        run_id=payload["run_id"],
                        org_id=payload.get("org_id"),
                    ),
                    poll_interval=float(os.getenv("AGENT_SDK_QUEUE_POLL_INTERVAL", "0.2")),
                    max_attempts=int(os.getenv("AGENT_SDK_QUEUE_MAX_ATTEMPTS", "3")),
                )
            elif queue_backend == "kafka":
                topic = os.getenv("AGENT_SDK_KAFKA_TOPIC", "agent-sdk-jobs")
                durable_queue = DurableExecutionQueue(
                    backend=KafkaQueueBackend(topic),
                    handler=lambda payload: runtime.run_async(
                        payload["task"],
                        session_id=payload["session_id"],
                        run_id=payload["run_id"],
                        org_id=payload.get("org_id"),
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
        hash_chain = None
        if audit_hash_chain_enabled and audit_path:
            hash_chain = AuditHashChain(AuditHashChain.load_last_hash(audit_path))
        audit_logger = create_audit_loggers(
            path=audit_path,
            emit_stdout=audit_stdout,
            redactor=redactor,
            hash_chain=hash_chain,
            http_endpoint=audit_http_endpoint,
            http_timeout_seconds=audit_http_timeout,
            extra_exporters=[WebhookAuditExporter(webhook_dispatcher)],
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
                project_id=os.getenv("API_KEY_PROJECT_ID"),
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
    app.state.provider_health = provider_health

    ui_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ui"))
    ui_source = os.path.join(ui_root, "index.html")
    ui_dist = os.path.join(ui_root, "dist", "index.html")

    def _resolve_ui_path() -> str:
        if os.path.exists(ui_dist):
            return ui_dist
        return ui_source

    def _org_id_from_request(request: Request, key_info: Optional[APIKeyInfo] = None) -> str:
        header_org = request.headers.get("X-Org-Id")
        if header_org:
            return header_org
        if key_info:
            return key_info.org_id
        return "default"

    def _project_id_from_request(request: Request, key_info: Optional[APIKeyInfo]) -> Optional[str]:
        header_project = request.headers.get("X-Project-Id")
        if key_info and key_info.project_id:
            if header_project and header_project != key_info.project_id:
                raise HTTPException(status_code=403, detail="Project scope mismatch")
            return key_info.project_id
        return header_project

    def _key_fingerprint(key: Optional[str]) -> Optional[str]:
        if not key:
            return None
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return digest[:12]

    def _audit_actor(request: Request) -> tuple[str, str]:
        api_key = request.headers.get("X-API-Key", "")
        info = get_api_key_manager().get_key_info(api_key)
        if info:
            return info.key, info.org_id
        return "unknown", "default"

    def _verify_scim_token(request: Request) -> None:
        token = os.getenv("AGENT_SDK_SCIM_TOKEN")
        if not token:
            raise HTTPException(status_code=503, detail="SCIM token not configured")
        auth_header = request.headers.get("Authorization", "")
        if auth_header != f"Bearer {token}":
            raise HTTPException(status_code=401, detail="Invalid SCIM token")

    async def _run_with_policies(task: str, session_id: str, run_id: str, org_id: str):
        async def _invoke():
            return await runtime.run_async(task, session_id=session_id, run_id=run_id, org_id=org_id)

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
                {"task": task, "session_id": session_id, "run_id": run_id, "org_id": org_id}
            )
        if execution_queue is not None:
            return await execution_queue.submit(_invoke_with_retry)
        return await _invoke_with_retry()

    def _assert_residency(org_id: str) -> None:
        server_region = os.getenv("AGENT_SDK_DATA_REGION")
        required = tenant_store.get_residency(org_id)
        if required and server_region and required != server_region:
            raise HTTPException(
                status_code=409,
                detail=f"Data residency mismatch: org requires {required}, server region {server_region}",
            )

    def _apply_retention(org_id: str) -> None:
        policy = tenant_store.get_retention_policy(org_id)
        now = datetime.now(timezone.utc)
        if policy.max_run_age_days:
            cutoff = now - timedelta(days=policy.max_run_age_days)
            storage.prune_runs(org_id, cutoff.isoformat())
        if policy.max_session_age_days:
            cutoff = now - timedelta(days=policy.max_session_age_days)
            storage.prune_sessions(org_id, cutoff.isoformat())

    def _load_audit_entries(path: Optional[str], org_id: Optional[str], limit: Optional[int]) -> list[dict]:
        if not path or not os.path.exists(path):
            return []
        entries: list[dict] = []
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if org_id and payload.get("org_id") != org_id:
                    continue
                entries.append(payload)
                if limit and len(entries) >= limit:
                    break
        return entries

    def _assert_model_policy(org_id: str, model_id: Optional[str]) -> None:
        decision = policy_engine.evaluate_model(org_id, model_id)
        if not decision.allowed:
            raise HTTPException(status_code=403, detail=f"Policy denied model: {decision.reason}")

    def _assert_provider_health(provider: Optional[str]) -> None:
        if not provider:
            return
        status = provider_health.check(provider)
        if not status.healthy:
            raise HTTPException(status_code=503, detail=f"Provider unhealthy: {status.reason}")

    async def _submit_scheduled(entry):
        org_id = entry.org_id
        _assert_residency(org_id)
        _apply_retention(org_id)
        allowed, reason = tenant_store.check_quota(
            org_id, new_session=True, new_run=True, project_id=project_id, key=key_info.key
        )
        if not allowed:
            logger.warning("Scheduled run blocked for org %s: %s", org_id, reason)
            return
        session_id = new_session_id()
        run_id = new_run_id()
        session = SessionMetadata(session_id=session_id, org_id=org_id)
        storage.create_session(session)
        tenant_store.record_session(org_id, project_id=project_id, key=key_info.key)
        requested_model = planner.context.model_config.model_id if planner.context.model_config else None
        resolved_model = tenant_store.resolve_model(org_id, requested_model)
        model_decision = policy_engine.evaluate_model(org_id, resolved_model)
        if not model_decision.allowed:
            logger.warning(
                "Scheduled run blocked for org %s due to model policy: %s",
                org_id,
                model_decision.reason,
            )
            return
        scheduled_metadata = {
            "request_id": f"schedule_{entry.schedule_id}",
            "trace_id": entry.schedule_id,
            "scheduled": True,
            "schedule_id": entry.schedule_id,
        }
        run_meta = RunMetadata(
            run_id=run_id,
            session_id=session_id,
            agent_id="planner-executor",
            org_id=org_id,
            status=RunStatus.RUNNING,
            model=resolved_model,
            metadata=scheduled_metadata,
        )
        storage.create_run(run_meta)
        tenant_store.record_run(org_id)
        try:
            msgs = await _run_with_policies(entry.task, session_id=session_id, run_id=run_id, org_id=org_id)
            token_count = sum(TokenCounter.count_tokens(m.content) for m in msgs)
            run_meta = RunMetadata(
                run_id=run_id,
                session_id=session_id,
                agent_id="planner-executor",
                org_id=org_id,
                status=RunStatus.COMPLETED,
                model=resolved_model,
                metadata={**scheduled_metadata, "token_count": token_count},
            )
            storage.update_run(run_meta)
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
                metadata={**scheduled_metadata, "error": str(exc)},
            )
            storage.update_run(run_meta)

    scheduler_store = None
    scheduler_db = os.getenv("AGENT_SDK_SCHEDULER_DB_PATH")
    if scheduler_db:
        scheduler_store = SQLiteSchedulerStore(scheduler_db)
    scheduler = Scheduler(
        _submit_scheduled,
        poll_interval=float(os.getenv("AGENT_SDK_SCHEDULER_POLL_INTERVAL", "1.0")),
        store=scheduler_store,
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
    async def correlation_id_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-Id") or f"req_{secrets.token_hex(8)}"
        trace_id = request.headers.get("X-Trace-Id") or request_id
        request.state.request_id = request_id
        request.state.trace_id = trace_id
        response = await call_next(request)
        response.headers["X-Request-Id"] = request_id
        response.headers["X-Trace-Id"] = trace_id
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
    app.state.archive_backend = archive_backend
    app.state.privacy_exporter = privacy_exporter
    app.state.tenant_store = tenant_store
    app.state.policy_engine = policy_engine
    app.state.webhook_dispatcher = webhook_dispatcher
    app.state.device_registry = device_registry
    app.state.audit_logger = audit_logger
    app.state.prompt_registry = prompt_registry
    app.state.execution_queue = execution_queue
    app.state.durable_queue = durable_queue
    app.state.retry_config = retry_config
    app.state.idempotency_store = idempotency_store
    app.state.identity_provider = identity_provider
    app.state.secret_rotation_task = None
    app.state.secret_rotation_enabled = secret_rotation_enabled
    app.state.secret_rotation_interval = secret_rotation_interval

    async def _secret_rotation_loop() -> None:
        interval = max(secret_rotation_interval, 1.0)
        logger.info("Secret rotation automation enabled (interval=%ss)", interval)
        while True:
            try:
                policies = tenant_store.list_secret_rotation_policies()
                due = find_due_policies(policies)
                if due:
                    count = emit_rotation_due(due, audit_logger, webhook_dispatcher)
                    logger.info("Secret rotation due emitted for %s policies", count)
            except asyncio.CancelledError:
                logger.info("Secret rotation automation stopped")
                raise
            except Exception:
                logger.exception("Secret rotation automation failed")
            await asyncio.sleep(interval)

    @app.on_event("startup")
    async def _start_workers():
        if durable_queue is not None:
            await durable_queue.start()
        await scheduler.start()
        if secret_rotation_enabled:
            app.state.secret_rotation_task = asyncio.create_task(_secret_rotation_loop())

    @app.on_event("shutdown")
    async def _stop_workers():
        task = app.state.secret_rotation_task
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
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

    @app.post("/auth/validate", tags=["Auth"])
    async def validate_identity(req: AuthValidateRequest):
        """Validate identity token via configured provider."""
        try:
            claims = app.state.identity_provider.validate(req.token)
        except Exception as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        mapping = load_group_mapping()
        mapped = mapping.map_groups(claims.groups)
        response = {
            "subject": claims.subject,
            "email": claims.email,
            "issuer": claims.issuer,
            "groups": claims.groups,
            "raw": claims.raw,
        }
        if mapped.get("role"):
            response["role"] = mapped["role"]
        if mapped.get("scopes"):
            response["scopes"] = mapped["scopes"]
        return response

    # Task Execution Endpoint
    @app.post(
        "/run",
        response_model=TaskResponse,
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_RUN_WRITE]))],
        tags=["Tasks"]
    )
    async def run_task(
        req: RunTaskRequest,
        request: Request,
        key_info: APIKeyInfo = Depends(get_api_key_info),
    ):
        """Execute a task using the planner-executor runtime
        
        Args:
            req: Task execution request with task description and optional config
            
        Returns:
            Task execution result with status and messages
        """
        try:
            logger.info(f"Executing task: {req.task[:100]}")
            org_id = _org_id_from_request(request, key_info)
            project_id = _project_id_from_request(request, key_info)
            if project_id:
                project = tenant_store.get_project(project_id)
                if not project or project.org_id != org_id:
                    raise HTTPException(status_code=404, detail="Project not found")
            _assert_residency(org_id)
            _apply_retention(org_id)
            idempotency_key = request.headers.get("Idempotency-Key")
            if idempotency_key:
                cached = idempotency_store.get(idempotency_key)
                if cached:
                    return TaskResponse(**cached)

            allowed, reason = tenant_store.check_quota(
                org_id, new_session=True, new_run=True, project_id=project_id, key=key_info.key
            )
            if not allowed:
                raise HTTPException(status_code=429, detail=f"Quota exceeded: {reason}")

            session_id = new_session_id()
            run_id = new_run_id()

            session = SessionMetadata(session_id=session_id, org_id=org_id)
            storage.create_session(session)
            webhook_dispatcher.dispatch(
                "session.created",
                {"session_id": session_id, "org_id": org_id, "project_id": project_id},
            )
            tenant_store.record_session(org_id, project_id=project_id, key=key_info.key)

            requested_model = planner.context.model_config.model_id if planner.context.model_config else None
            resolved_model = tenant_store.resolve_model(org_id, requested_model)
            _assert_model_policy(org_id, resolved_model)
            _assert_provider_health(planner.context.model_config.provider if planner.context.model_config else None)
            run_metadata = {
                "request_id": request.state.request_id,
                "trace_id": request.state.trace_id,
            }
            if req.lineage:
                run_metadata["lineage"] = req.lineage
            run_tags = dict(req.tags or {})
            if project_id:
                run_tags.setdefault("project_id", project_id)
            key_fingerprint = _key_fingerprint(key_info.key)
            if key_fingerprint:
                run_tags.setdefault("api_key_fingerprint", key_fingerprint)
            run_meta = RunMetadata(
                run_id=run_id,
                session_id=session_id,
                agent_id="planner-executor",
                org_id=org_id,
                status=RunStatus.RUNNING,
                model=resolved_model,
                tags=run_tags,
                metadata=run_metadata,
            )
            storage.create_run(run_meta)
            tenant_store.record_run(org_id, project_id=project_id, key=key_info.key)

            msgs = await _run_with_policies(req.task, session_id=session_id, run_id=run_id, org_id=org_id)
            token_count = sum(TokenCounter.count_tokens(m.content) for m in msgs)
            run_metadata["token_count"] = token_count
            run_meta = RunMetadata(
                run_id=run_id,
                session_id=session_id,
                agent_id="planner-executor",
                org_id=org_id,
                status=RunStatus.COMPLETED,
                model=resolved_model,
                tags=run_tags,
                metadata=run_metadata,
            )
            storage.update_run(run_meta)
            tenant_store.record_tokens(org_id, token_count, project_id=project_id, key=key_info.key)
            webhook_dispatcher.dispatch(
                "run.completed",
                {
                    "run_id": run_id,
                    "session_id": session_id,
                    "org_id": org_id,
                    "project_id": project_id,
                    "status": "completed",
                },
            )
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
            if "run_id" in locals():
                webhook_dispatcher.dispatch(
                    "run.failed",
                    {"run_id": run_id, "session_id": session_id, "org_id": org_id, "error": str(e)},
                )
            raise HTTPException(
                status_code=500,
                detail=_hinted_detail(
                    f"Task execution failed: {str(e)}",
                    "Review logs for stack trace and configuration issues.",
                ),
            )
        except Exception as e:
            logger.error(f"Unexpected error during task execution: {e}", exc_info=True)
            if "run_id" in locals():
                webhook_dispatcher.dispatch(
                    "run.failed",
                    {"run_id": run_id, "session_id": session_id, "org_id": org_id, "error": str(e)},
                )
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
    async def run_task_stream(
        req: RunTaskRequest,
        request: Request,
        key_info: APIKeyInfo = Depends(get_api_key_info),
    ):
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

                msgs = await _run_with_policies(req.task, session_id=session_id, run_id=run_id, org_id=org_id)
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
                token_count = sum(TokenCounter.count_tokens(m.content) for m in msgs)
                completed_metadata = dict(run_metadata)
                completed_metadata["token_count"] = token_count
                storage.update_run(
                    RunMetadata(
                        run_id=run_id,
                        session_id=session_id,
                        agent_id="planner-executor",
                        status=RunStatus.COMPLETED,
                        model=model_id,
                        tags=run_tags,
                        metadata=completed_metadata,
                    )
                )
                tenant_store.record_tokens(org_id, token_count)
                webhook_dispatcher.dispatch(
                    "run.completed",
                    {
                        "run_id": run_id,
                        "session_id": session_id,
                        "org_id": org_id,
                        "project_id": project_id,
                        "status": "completed",
                    },
                )
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
                        tags=run_tags,
                        metadata=run_metadata,
                    )
                )
                webhook_dispatcher.dispatch(
                    "run.failed",
                    {
                        "run_id": run_id,
                        "session_id": session_id,
                        "org_id": org_id,
                        "project_id": project_id,
                        "error": str(e),
                    },
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

        org_id = _org_id_from_request(request, key_info)
        project_id = _project_id_from_request(request, key_info)
        if project_id:
            project = tenant_store.get_project(project_id)
            if not project or project.org_id != org_id:
                raise HTTPException(status_code=404, detail="Project not found")
        allowed, reason = tenant_store.check_quota(
            org_id, new_session=True, new_run=True, project_id=project_id, key=key_info.key
        )
        if not allowed:
            raise HTTPException(status_code=429, detail=f"Quota exceeded: {reason}")
        run_id = new_run_id()
        session_id = new_session_id()
        storage.create_session(SessionMetadata(session_id=session_id, org_id=org_id))
        webhook_dispatcher.dispatch(
            "session.created",
            {"session_id": session_id, "org_id": org_id, "project_id": project_id},
        )
        tenant_store.record_session(org_id, project_id=project_id, key=key_info.key)
        requested_model = planner.context.model_config.model_id if planner.context.model_config else None
        resolved_model = tenant_store.resolve_model(org_id, requested_model)
        _assert_model_policy(org_id, resolved_model)
        _assert_provider_health(planner.context.model_config.provider if planner.context.model_config else None)
        run_tags = dict(req.tags or {})
        if project_id:
            run_tags.setdefault("project_id", project_id)
        key_fingerprint = _key_fingerprint(key_info.key)
        if key_fingerprint:
            run_tags.setdefault("api_key_fingerprint", key_fingerprint)
        key_fingerprint = _key_fingerprint(key_info.key)
        if key_fingerprint:
            run_tags.setdefault("api_key_fingerprint", key_fingerprint)
        run_metadata = {
            "request_id": request.state.request_id,
            "trace_id": request.state.trace_id,
        }
        if req.lineage:
            run_metadata["lineage"] = req.lineage
        storage.create_run(
            RunMetadata(
                run_id=run_id,
                session_id=session_id,
                agent_id="planner-executor",
                org_id=org_id,
                status=RunStatus.RUNNING,
                model=resolved_model,
                tags=run_tags,
                metadata=run_metadata,
            )
        )
        tenant_store.record_run(org_id, project_id=project_id, key=key_info.key)
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
    async def channel_webhook(
        req: ChannelMessageRequest,
        request: Request,
        key_info: APIKeyInfo = Depends(get_api_key_info),
    ):
        if req.channel != "web":
            raise HTTPException(status_code=400, detail="Unsupported channel")
        org_id = _org_id_from_request(request, key_info)
        project_id = _project_id_from_request(request, key_info)
        if project_id:
            project = tenant_store.get_project(project_id)
            if not project or project.org_id != org_id:
                raise HTTPException(status_code=404, detail="Project not found")
        if req.session_id is None or storage.get_session(req.session_id) is None:
            tenant_store.record_session(org_id, project_id=project_id, key=key_info.key)
        tenant_store.record_run(org_id, project_id=project_id, key=key_info.key)
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
        "/admin/projects",
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_ADMIN]))],
        tags=["Admin"],
    )
    async def list_projects(request: Request, org_id: Optional[str] = None):
        actor, audit_org = _audit_actor(request)
        audit_logger.emit(
            AuditLogEntry(
                action="admin.projects.list",
                actor=actor,
                org_id=audit_org,
                target_type="project",
                metadata={"filter_org_id": org_id} if org_id else {},
            )
        )
        return [asdict(project) for project in tenant_store.list_projects(org_id)]

    @app.post(
        "/admin/projects",
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_ADMIN]))],
        tags=["Admin"],
    )
    async def create_project(req: ProjectCreateRequest, request: Request):
        project = tenant_store.create_project(req.org_id, req.name, tags=req.tags)
        actor, audit_org = _audit_actor(request)
        audit_logger.emit(
            AuditLogEntry(
                action="admin.projects.create",
                actor=actor,
                org_id=audit_org,
                target_type="project",
                target_id=project.project_id,
                metadata=asdict(project),
            )
        )
        return asdict(project)

    @app.delete(
        "/admin/projects/{project_id}",
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_ADMIN]))],
        tags=["Admin"],
    )
    async def delete_project(project_id: str, request: Request):
        deleted = tenant_store.delete_project(project_id)
        actor, audit_org = _audit_actor(request)
        audit_logger.emit(
            AuditLogEntry(
                action="admin.projects.delete",
                actor=actor,
                org_id=audit_org,
                target_type="project",
                target_id=project_id,
                metadata={"deleted": deleted},
            )
        )
        return {"deleted": bool(deleted)}

    @app.get(
        "/admin/webhooks",
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_ADMIN]))],
        tags=["Admin"],
    )
    async def list_webhooks(request: Request, org_id: Optional[str] = None):
        actor, audit_org = _audit_actor(request)
        audit_logger.emit(
            AuditLogEntry(
                action="admin.webhooks.list",
                actor=actor,
                org_id=audit_org,
                target_type="webhook",
                metadata={"filter_org_id": org_id} if org_id else {},
            )
        )
        return [asdict(sub) for sub in tenant_store.list_webhook_subscriptions(org_id)]

    @app.post(
        "/admin/webhooks",
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_ADMIN]))],
        tags=["Admin"],
    )
    async def create_webhook(req: WebhookSubscriptionRequest, request: Request):
        subscription = WebhookSubscription(
            subscription_id=f"wh_{secrets.token_hex(6)}",
            org_id=req.org_id,
            url=req.url,
            event_types=req.event_types,
            secret=req.secret,
            created_at=datetime.now(timezone.utc).isoformat(),
            active=req.active,
            max_attempts=req.max_attempts,
            backoff_seconds=req.backoff_seconds,
        )
        stored = tenant_store.create_webhook_subscription(subscription)
        webhook_dispatcher.update_subscriptions(tenant_store.list_webhook_subscriptions())
        actor, audit_org = _audit_actor(request)
        audit_logger.emit(
            AuditLogEntry(
                action="admin.webhooks.create",
                actor=actor,
                org_id=audit_org,
                target_type="webhook",
                target_id=stored.subscription_id,
                metadata={"url": stored.url, "event_types": stored.event_types},
            )
        )
        return asdict(stored)

    @app.delete(
        "/admin/webhooks/{subscription_id}",
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_ADMIN]))],
        tags=["Admin"],
    )
    async def delete_webhook(subscription_id: str, request: Request):
        removed = tenant_store.delete_webhook_subscription(subscription_id)
        webhook_dispatcher.update_subscriptions(tenant_store.list_webhook_subscriptions())
        actor, audit_org = _audit_actor(request)
        audit_logger.emit(
            AuditLogEntry(
                action="admin.webhooks.delete",
                actor=actor,
                org_id=audit_org,
                target_type="webhook",
                target_id=subscription_id,
                metadata={"removed": removed},
            )
        )
        if not removed:
            raise HTTPException(status_code=404, detail="Webhook not found")
        return {"deleted": True}

    @app.get(
        "/admin/webhooks/dlq",
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_ADMIN]))],
        tags=["Admin"],
    )
    async def list_webhook_dlq(request: Request):
        actor, audit_org = _audit_actor(request)
        audit_logger.emit(
            AuditLogEntry(
                action="admin.webhooks.dlq.list",
                actor=actor,
                org_id=audit_org,
                target_type="webhook_dlq",
            )
        )
        return [delivery.__dict__ for delivery in webhook_dispatcher.list_dlq()]

    @app.get(
        "/admin/secrets/rotation",
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_ADMIN]))],
        tags=["Admin"],
    )
    async def list_secret_rotation(request: Request, org_id: Optional[str] = None):
        actor, audit_org = _audit_actor(request)
        audit_logger.emit(
            AuditLogEntry(
                action="admin.secrets.rotation.list",
                actor=actor,
                org_id=audit_org,
                target_type="secret_rotation",
                metadata={"filter_org_id": org_id} if org_id else {},
            )
        )
        return [asdict(policy) for policy in tenant_store.list_secret_rotation_policies(org_id)]

    @app.post(
        "/admin/secrets/rotation",
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_ADMIN]))],
        tags=["Admin"],
    )
    async def set_secret_rotation(req: SecretRotationRequest, request: Request):
        policy = tenant_store.set_secret_rotation_policy(
            req.org_id,
            req.secret_id,
            req.rotation_days,
            last_rotated_at=req.last_rotated_at,
        )
        actor, audit_org = _audit_actor(request)
        audit_logger.emit(
            AuditLogEntry(
                action="admin.secrets.rotation.set",
                actor=actor,
                org_id=audit_org,
                target_type="secret_rotation",
                target_id=req.secret_id,
                metadata=req.model_dump(),
            )
        )
        return asdict(policy)

    @app.get(
        "/admin/secrets/health",
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_ADMIN]))],
        tags=["Admin"],
    )
    async def secret_health(request: Request, org_id: Optional[str] = None):
        policies = tenant_store.list_secret_rotation_policies(org_id)
        now = datetime.now(timezone.utc)
        results = []
        for policy in policies:
            last = None
            if policy.last_rotated_at:
                try:
                    last = datetime.fromisoformat(policy.last_rotated_at)
                except ValueError:
                    last = None
            age_days = None
            if last:
                age_days = (now - last).days
            due = age_days is not None and age_days >= policy.rotation_days
            results.append(
                {
                    "secret_id": policy.secret_id,
                    "org_id": policy.org_id,
                    "rotation_days": policy.rotation_days,
                    "last_rotated_at": policy.last_rotated_at,
                    "age_days": age_days,
                    "due": due,
                }
            )
        return {"results": results, "count": len(results)}

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
        if req.project_id:
            project = tenant_store.get_project(req.project_id)
            if not project or project.org_id != req.org_id:
                raise HTTPException(status_code=404, detail="Project not found")
        record = tenant_store.create_api_key(
            req.org_id,
            req.label,
            role=req.role,
            scopes=req.scopes,
            expires_at=req.expires_at,
            rate_limit_per_minute=req.rate_limit_per_minute,
            ip_allowlist=req.ip_allowlist,
            project_id=req.project_id,
        )
        get_api_key_manager().add_key(
            record.key,
            role=req.role,
            scopes=req.scopes,
            org_id=req.org_id,
            project_id=req.project_id,
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
                metadata={
                    "label": req.label,
                    "role": req.role,
                    "scopes": req.scopes,
                    "project_id": req.project_id,
                },
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

    @app.delete(
        "/admin/api-keys/{key_id}",
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_ADMIN]))],
        tags=["Admin"],
    )
    async def delete_api_key(key_id: str, request: Request):
        record = next((r for r in tenant_store.list_api_keys() if r.key_id == key_id), None)
        deleted = tenant_store.delete_api_key(key_id)
        if deleted and record:
            get_api_key_manager().remove_key(record.key)
        actor, _ = _audit_actor(request)
        audit_logger.emit(
            AuditLogEntry(
                action="api_key.deleted",
                actor=actor,
                org_id=record.org_id if record else "default",
                target_type="api_key",
                target_id=key_id,
                metadata={"deleted": deleted},
            )
        )
        return {"deleted": bool(deleted)}

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
        "/admin/usage/projects",
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_ADMIN]))],
        tags=["Admin"],
    )
    async def project_usage_summary(request: Request, project_id: Optional[str] = None):
        actor, audit_org = _audit_actor(request)
        audit_logger.emit(
            AuditLogEntry(
                action="admin.usage.projects.list",
                actor=actor,
                org_id=audit_org,
                target_type="usage",
                metadata={"project_id": project_id} if project_id else {},
            )
        )
        return [asdict(summary) for summary in tenant_store.project_usage_summary(project_id)]

    @app.get(
        "/admin/usage/api-keys",
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_ADMIN]))],
        tags=["Admin"],
    )
    async def api_key_usage_summary(request: Request, key: Optional[str] = None):
        actor, audit_org = _audit_actor(request)
        audit_logger.emit(
            AuditLogEntry(
                action="admin.usage.api_keys.list",
                actor=actor,
                org_id=audit_org,
                target_type="usage",
                metadata={"key": key} if key else {},
            )
        )
        return [asdict(summary) for summary in tenant_store.api_key_usage_summary(key)]

    @app.get(
        "/admin/providers/health",
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_ADMIN]))],
        tags=["Admin"],
    )
    async def provider_health_status(request: Request):
        actor, audit_org = _audit_actor(request)
        audit_logger.emit(
            AuditLogEntry(
                action="admin.providers.health",
                actor=actor,
                org_id=audit_org,
                target_type="provider_health",
            )
        )
        providers = []
        if planner.context.model_config:
            providers.append(planner.context.model_config.provider)
        if executor.context.model_config:
            providers.append(executor.context.model_config.provider)
        results = [status.__dict__ for status in provider_health.check_all(list(set(providers)))]
        return {"providers": results}

    @app.get(
        "/admin/usage/export",
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_ADMIN]))],
        tags=["Admin"],
    )
    async def usage_export(
        request: Request,
        format: str = "json",
        org_id: Optional[str] = None,
        group_by: str = "org_id",
        limit: int = 1000,
    ):
        actor, audit_org = _audit_actor(request)
        audit_logger.emit(
            AuditLogEntry(
                action="admin.usage.export",
                actor=actor,
                org_id=audit_org,
                target_type="usage",
                metadata={"filter_org_id": org_id, "group_by": group_by, "limit": limit},
            )
        )
        group_fields = [field.strip() for field in group_by.split(",") if field.strip()]
        runs = storage.list_runs(org_id=org_id, limit=limit)
        aggregate: Dict[tuple, Dict[str, Any]] = {}
        session_sets: Dict[tuple, set] = {}
        for run in runs:
            key_parts = []
            for field in group_fields:
                if field == "org_id":
                    key_parts.append(run.org_id)
                else:
                    key_parts.append(run.tags.get(field, "unknown"))
            key = tuple(key_parts)
            session_sets.setdefault(key, set()).add(run.session_id)
            entry = aggregate.setdefault(
                key,
                {
                    "run_count": 0,
                    "session_count": 0,
                    "token_count": 0,
                },
            )
            entry["run_count"] += 1
            entry["token_count"] += int(run.metadata.get("token_count", 0) or 0)
        for key, entry in aggregate.items():
            entry["session_count"] = len(session_sets.get(key, set()))
        results = []
        for key, entry in aggregate.items():
            row = {field: key[idx] for idx, field in enumerate(group_fields)}
            row.update(entry)
            results.append(row)
        if format.lower() == "csv":
            output = io.StringIO()
            writer = csv.writer(output)
            header = group_fields + ["run_count", "session_count", "token_count"]
            writer.writerow(header)
            for row in results:
                writer.writerow([row.get(col) for col in header])
            return Response(output.getvalue(), media_type="text/csv")
        if format.lower() != "json":
            raise HTTPException(status_code=400, detail="format must be json or csv")
        return {"results": results, "count": len(results)}

    @app.post(
        "/admin/archives/export",
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_ADMIN]))],
        tags=["Admin"],
    )
    async def export_archive(
        request: Request,
        run_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ):
        if not run_id and not session_id:
            raise HTTPException(status_code=400, detail="run_id or session_id required")
        if run_id and session_id:
            raise HTTPException(status_code=400, detail="provide only one of run_id or session_id")
        actor, audit_org = _audit_actor(request)
        if run_id:
            path = archive_backend.export_run(storage, run_id)
            audit_logger.emit(
                AuditLogEntry(
                    action="admin.archive.export_run",
                    actor=actor,
                    org_id=audit_org,
                    target_type="archive",
                    target_id=run_id,
                    metadata={"path": path},
                )
            )
            return {"path": path}
        path = archive_backend.export_session(storage, session_id)  # type: ignore[arg-type]
        audit_logger.emit(
            AuditLogEntry(
                action="admin.archive.export_session",
                actor=actor,
                org_id=audit_org,
                target_type="archive",
                target_id=session_id,
                metadata={"path": path},
            )
        )
        return {"path": path}

    @app.post(
        "/admin/archives/restore",
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_ADMIN]))],
        tags=["Admin"],
    )
    async def restore_archive(request: Request, path: str):
        if not path:
            raise HTTPException(status_code=400, detail="path required")
        archive_backend.restore(storage, path)
        actor, audit_org = _audit_actor(request)
        audit_logger.emit(
            AuditLogEntry(
                action="admin.archive.restore",
                actor=actor,
                org_id=audit_org,
                target_type="archive",
                metadata={"path": path},
            )
        )
        return {"restored": True}

    @app.post(
        "/admin/privacy/export",
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_ADMIN]))],
        tags=["Admin"],
    )
    async def export_privacy_bundle(req: PrivacyExportRequest, request: Request):
        path = privacy_exporter.export_org_bundle(
            storage,
            req.org_id,
            user_id=req.user_id,
            audit_log_path=os.getenv("AGENT_SDK_AUDIT_LOG_PATH") if req.include_audit_logs else None,
        )
        actor, audit_org = _audit_actor(request)
        audit_logger.emit(
            AuditLogEntry(
                action="admin.privacy.export",
                actor=actor,
                org_id=audit_org,
                target_type="privacy_bundle",
                metadata=req.model_dump(),
            )
        )
        return {"path": path}

    @app.get(
        "/admin/users",
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_ADMIN]))],
        tags=["Admin"],
    )
    async def list_users(request: Request, org_id: Optional[str] = None, active_only: bool = False):
        actor, audit_org = _audit_actor(request)
        audit_logger.emit(
            AuditLogEntry(
                action="admin.users.list",
                actor=actor,
                org_id=audit_org,
                target_type="user",
                metadata={"filter_org_id": org_id, "active_only": active_only},
            )
        )
        return [asdict(user) for user in tenant_store.list_users(org_id, active_only=active_only)]

    @app.post(
        "/admin/users",
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_ADMIN]))],
        tags=["Admin"],
    )
    async def create_user(req: UserCreateRequest, request: Request):
        user = tenant_store.create_user(req.org_id, req.name)
        actor, audit_org = _audit_actor(request)
        audit_logger.emit(
            AuditLogEntry(
                action="admin.users.create",
                actor=actor,
                org_id=audit_org,
                target_type="user",
                target_id=user.user_id,
                metadata=asdict(user),
            )
        )
        return asdict(user)

    @app.post(
        "/admin/service-accounts",
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_ADMIN]))],
        tags=["Admin"],
    )
    async def create_service_account(req: ServiceAccountCreateRequest, request: Request):
        user = tenant_store.create_user(req.org_id, req.name, is_service_account=True)
        actor, audit_org = _audit_actor(request)
        audit_logger.emit(
            AuditLogEntry(
                action="admin.service_accounts.create",
                actor=actor,
                org_id=audit_org,
                target_type="service_account",
                target_id=user.user_id,
                metadata=asdict(user),
            )
        )
        return asdict(user)

    @app.delete(
        "/admin/users/{user_id}",
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_ADMIN]))],
        tags=["Admin"],
    )
    async def deactivate_user(user_id: str, request: Request):
        removed = tenant_store.deactivate_user(user_id)
        actor, audit_org = _audit_actor(request)
        audit_logger.emit(
            AuditLogEntry(
                action="admin.users.deactivate",
                actor=actor,
                org_id=audit_org,
                target_type="user",
                target_id=user_id,
                metadata={"deactivated": removed},
            )
        )
        if not removed:
            raise HTTPException(status_code=404, detail="User not found")
        return {"user_id": user_id, "deactivated": True}

    @app.get("/scim/v2/Users", tags=["SCIM"])
    async def scim_list_users(request: Request):
        _verify_scim_token(request)
        users = tenant_store.list_users()
        resources = [
            {
                "id": user.user_id,
                "userName": user.name,
                "active": user.active,
                "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User": {
                    "orgId": user.org_id,
                    "serviceAccount": user.is_service_account,
                },
            }
            for user in users
        ]
        return {
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
            "totalResults": len(resources),
            "startIndex": 1,
            "itemsPerPage": len(resources),
            "Resources": resources,
        }

    @app.post("/scim/v2/Users", tags=["SCIM"])
    async def scim_create_user(request: Request):
        _verify_scim_token(request)
        payload = await request.json()
        user_name = payload.get("userName") or payload.get("name", {}).get("formatted", "unknown")
        org_id = payload.get("urn:ietf:params:scim:schemas:extension:enterprise:2.0:User", {}).get(
            "orgId", "default"
        )
        is_service_account = payload.get(
            "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User", {}
        ).get("serviceAccount", False)
        user = tenant_store.create_user(org_id, user_name, is_service_account=bool(is_service_account))
        return {
            "id": user.user_id,
            "userName": user.name,
            "active": user.active,
            "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User": {
                "orgId": user.org_id,
                "serviceAccount": user.is_service_account,
            },
        }

    @app.delete("/scim/v2/Users/{user_id}", tags=["SCIM"])
    async def scim_delete_user(user_id: str, request: Request):
        _verify_scim_token(request)
        removed = tenant_store.deactivate_user(user_id)
        if not removed:
            raise HTTPException(status_code=404, detail="User not found")
        return {"id": user_id, "active": False}

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
        "/admin/quotas/projects",
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_ADMIN]))],
        tags=["Admin"],
    )
    async def get_project_quota(request: Request, project_id: Optional[str] = None):
        actor, audit_org = _audit_actor(request)
        audit_logger.emit(
            AuditLogEntry(
                action="admin.quotas.projects.get",
                actor=actor,
                org_id=audit_org,
                target_type="project_quota",
                metadata={"project_id": project_id} if project_id else {},
            )
        )
        if not project_id:
            return {"quotas": []}
        quota = tenant_store.get_project_quota(project_id)
        return {"project_id": project_id, **quota.__dict__}

    @app.post(
        "/admin/quotas/projects",
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_ADMIN]))],
        tags=["Admin"],
    )
    async def set_project_quota(req: ProjectQuotaUpdateRequest, request: Request):
        tenant_store.set_project_quota(
            req.project_id,
            QuotaLimits(max_runs=req.max_runs, max_sessions=req.max_sessions, max_tokens=req.max_tokens),
        )
        actor, audit_org = _audit_actor(request)
        audit_logger.emit(
            AuditLogEntry(
                action="admin.quotas.projects.set",
                actor=actor,
                org_id=audit_org,
                target_type="project_quota",
                target_id=req.project_id,
                metadata=req.model_dump(),
            )
        )
        quota = tenant_store.get_project_quota(req.project_id)
        return {"project_id": req.project_id, **quota.__dict__}

    @app.get(
        "/admin/quotas/api-keys",
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_ADMIN]))],
        tags=["Admin"],
    )
    async def get_api_key_quota(request: Request, key: Optional[str] = None):
        actor, audit_org = _audit_actor(request)
        audit_logger.emit(
            AuditLogEntry(
                action="admin.quotas.api_keys.get",
                actor=actor,
                org_id=audit_org,
                target_type="api_key_quota",
                metadata={"key": key} if key else {},
            )
        )
        if not key:
            return {"quotas": []}
        quota = tenant_store.get_api_key_quota(key)
        return {"key": key, **quota.__dict__}

    @app.post(
        "/admin/quotas/api-keys",
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_ADMIN]))],
        tags=["Admin"],
    )
    async def set_api_key_quota(req: APIKeyQuotaUpdateRequest, request: Request):
        tenant_store.set_api_key_quota(
            req.key,
            QuotaLimits(max_runs=req.max_runs, max_sessions=req.max_sessions, max_tokens=req.max_tokens),
        )
        actor, audit_org = _audit_actor(request)
        audit_logger.emit(
            AuditLogEntry(
                action="admin.quotas.api_keys.set",
                actor=actor,
                org_id=audit_org,
                target_type="api_key_quota",
                target_id=req.key,
                metadata=req.model_dump(),
            )
        )
        quota = tenant_store.get_api_key_quota(req.key)
        return {"key": req.key, **quota.__dict__}

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
            return {
                "org_id": org_id,
                "max_events": policy.max_events,
                "max_run_age_days": policy.max_run_age_days,
                "max_session_age_days": policy.max_session_age_days,
            }
        return [
            {
                "org_id": org.org_id,
                "max_events": tenant_store.get_retention_policy(org.org_id).max_events,
                "max_run_age_days": tenant_store.get_retention_policy(org.org_id).max_run_age_days,
                "max_session_age_days": tenant_store.get_retention_policy(org.org_id).max_session_age_days,
            }
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
            RetentionPolicyConfig(
                max_events=req.max_events,
                max_run_age_days=req.max_run_age_days,
                max_session_age_days=req.max_session_age_days,
            ),
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
        return {
            "org_id": req.org_id,
            "max_events": policy.max_events,
            "max_run_age_days": policy.max_run_age_days,
            "max_session_age_days": policy.max_session_age_days,
        }

    @app.get(
        "/admin/residency",
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_ADMIN]))],
        tags=["Admin"],
    )
    async def get_residency(request: Request, org_id: Optional[str] = None):
        actor, audit_org = _audit_actor(request)
        audit_logger.emit(
            AuditLogEntry(
                action="admin.residency.get",
                actor=actor,
                org_id=audit_org,
                target_type="residency",
                metadata={"filter_org_id": org_id} if org_id else {},
            )
        )
        if org_id:
            return {"org_id": org_id, "region": tenant_store.get_residency(org_id)}
        return [
            {"org_id": org.org_id, "region": tenant_store.get_residency(org.org_id)}
            for org in tenant_store.list_orgs()
        ]

    @app.post(
        "/admin/residency",
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_ADMIN]))],
        tags=["Admin"],
    )
    async def set_residency(req: ResidencyRequest, request: Request):
        tenant_store.set_residency(req.org_id, req.region)
        actor, audit_org = _audit_actor(request)
        audit_logger.emit(
            AuditLogEntry(
                action="admin.residency.set",
                actor=actor,
                org_id=audit_org,
                target_type="residency",
                metadata=req.model_dump(),
            )
        )
        return {"org_id": req.org_id, "region": tenant_store.get_residency(req.org_id)}

    @app.get(
        "/admin/encryption-keys",
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_ADMIN]))],
        tags=["Admin"],
    )
    async def get_encryption_key(request: Request, org_id: Optional[str] = None):
        actor, audit_org = _audit_actor(request)
        audit_logger.emit(
            AuditLogEntry(
                action="admin.encryption_keys.get",
                actor=actor,
                org_id=audit_org,
                target_type="encryption_key",
                metadata={"filter_org_id": org_id} if org_id else {},
            )
        )
        if org_id:
            return {"org_id": org_id, "key": tenant_store.get_encryption_key(org_id)}
        return [
            {"org_id": org.org_id, "key": tenant_store.get_encryption_key(org.org_id)}
            for org in tenant_store.list_orgs()
        ]

    @app.post(
        "/admin/encryption-keys",
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_ADMIN]))],
        tags=["Admin"],
    )
    async def set_encryption_key(req: EncryptionKeyRequest, request: Request):
        key = req.key or generate_key()
        tenant_store.set_encryption_key(req.org_id, key)
        actor, audit_org = _audit_actor(request)
        audit_logger.emit(
            AuditLogEntry(
                action="admin.encryption_keys.set",
                actor=actor,
                org_id=audit_org,
                target_type="encryption_key",
                metadata={"org_id": req.org_id},
            )
        )
        return {"org_id": req.org_id, "key": key}

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
        "/admin/policy-bundles",
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_ADMIN]))],
        tags=["Admin"],
    )
    async def list_policy_bundles(request: Request):
        actor, audit_org = _audit_actor(request)
        audit_logger.emit(
            AuditLogEntry(
                action="admin.policy_bundles.list",
                actor=actor,
                org_id=audit_org,
                target_type="policy_bundle",
            )
        )
        return {"bundles": [bundle.__dict__ for bundle in tenant_store.list_policy_bundles()]}

    @app.post(
        "/admin/policy-bundles",
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_ADMIN]))],
        tags=["Admin"],
    )
    async def create_policy_bundle(req: PolicyBundleCreateRequest, request: Request):
        errors = validate_policy_content(req.content)
        if errors:
            raise HTTPException(status_code=422, detail={"errors": errors})
        bundle = tenant_store.create_policy_bundle(
            req.bundle_id,
            content=req.content,
            description=req.description,
            version=req.version,
        )
        actor, audit_org = _audit_actor(request)
        audit_logger.emit(
            AuditLogEntry(
                action="admin.policy_bundles.create",
                actor=actor,
                org_id=audit_org,
                target_type="policy_bundle",
                target_id=req.bundle_id,
                metadata={"version": bundle.version},
            )
        )
        return bundle.__dict__

    @app.post(
        "/admin/policy-presets",
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_ADMIN]))],
        tags=["Admin"],
    )
    async def create_policy_preset(req: PolicyPresetRequest, request: Request):
        preset_content = safety_preset(req.preset)
        bundle = tenant_store.create_policy_bundle(
            req.bundle_id,
            content=preset_content,
            description=req.description or f"Safety preset: {req.preset}",
            version=None,
        )
        actor, audit_org = _audit_actor(request)
        audit_logger.emit(
            AuditLogEntry(
                action="admin.policy_presets.create",
                actor=actor,
                org_id=audit_org,
                target_type="policy_preset",
                target_id=req.bundle_id,
                metadata={"preset": req.preset, "version": bundle.version},
            )
        )
        return bundle.__dict__

    @app.get(
        "/admin/policy-bundles/{bundle_id}",
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_ADMIN]))],
        tags=["Admin"],
    )
    async def list_policy_bundle_versions(bundle_id: str, request: Request):
        actor, audit_org = _audit_actor(request)
        audit_logger.emit(
            AuditLogEntry(
                action="admin.policy_bundles.versions",
                actor=actor,
                org_id=audit_org,
                target_type="policy_bundle",
                target_id=bundle_id,
            )
        )
        return {
            "bundle_id": bundle_id,
            "versions": [bundle.__dict__ for bundle in tenant_store.list_policy_bundle_versions(bundle_id)],
        }

    @app.get(
        "/admin/policy-bundles/{bundle_id}/latest",
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_ADMIN]))],
        tags=["Admin"],
    )
    async def get_latest_policy_bundle(bundle_id: str, request: Request):
        actor, audit_org = _audit_actor(request)
        audit_logger.emit(
            AuditLogEntry(
                action="admin.policy_bundles.latest",
                actor=actor,
                org_id=audit_org,
                target_type="policy_bundle",
                target_id=bundle_id,
            )
        )
        bundle = tenant_store.get_policy_bundle(bundle_id)
        if not bundle:
            raise HTTPException(status_code=404, detail="Policy bundle not found")
        return bundle.__dict__

    @app.get(
        "/admin/policy-approvals",
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_ADMIN]))],
        tags=["Admin"],
    )
    async def list_policy_approvals(
        request: Request,
        bundle_id: Optional[str] = None,
        status: Optional[str] = None,
        org_id: Optional[str] = None,
    ):
        actor, audit_org = _audit_actor(request)
        audit_logger.emit(
            AuditLogEntry(
                action="admin.policy_approvals.list",
                actor=actor,
                org_id=audit_org,
                target_type="policy_approval",
                metadata={"bundle_id": bundle_id, "status": status, "org_id": org_id},
            )
        )
        approvals = tenant_store.list_policy_approvals(bundle_id=bundle_id, status=status, org_id=org_id)
        return {"approvals": [approval.__dict__ for approval in approvals]}

    @app.post(
        "/admin/policy-approvals",
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_ADMIN]))],
        tags=["Admin"],
    )
    async def submit_policy_approval(req: PolicyApprovalSubmitRequest, request: Request):
        approval = tenant_store.submit_policy_approval(
            req.bundle_id,
            req.version,
            submitted_by=req.submitted_by,
            notes=req.notes,
            org_id=req.org_id,
        )
        actor, audit_org = _audit_actor(request)
        audit_logger.emit(
            AuditLogEntry(
                action="admin.policy_approvals.submit",
                actor=actor,
                org_id=audit_org,
                target_type="policy_approval",
                target_id=req.bundle_id,
                metadata=req.model_dump(),
            )
        )
        return approval.__dict__

    @app.post(
        "/admin/policy-approvals/review",
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_ADMIN]))],
        tags=["Admin"],
    )
    async def review_policy_approval(req: PolicyApprovalReviewRequest, request: Request):
        approval = tenant_store.review_policy_approval(
            req.bundle_id,
            req.version,
            status=req.status,
            reviewed_by=req.reviewed_by,
            notes=req.notes,
            org_id=req.org_id,
        )
        actor, audit_org = _audit_actor(request)
        audit_logger.emit(
            AuditLogEntry(
                action="admin.policy_approvals.review",
                actor=actor,
                org_id=audit_org,
                target_type="policy_approval",
                target_id=req.bundle_id,
                metadata=req.model_dump(),
            )
        )
        return approval.__dict__

    @app.get(
        "/admin/policy-assignments",
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_ADMIN]))],
        tags=["Admin"],
    )
    async def list_policy_assignments(request: Request, org_id: Optional[str] = None):
        actor, audit_org = _audit_actor(request)
        audit_logger.emit(
            AuditLogEntry(
                action="admin.policy_assignments.list",
                actor=actor,
                org_id=audit_org,
                target_type="policy_assignment",
            )
        )
        if org_id:
            assignment = tenant_store.get_policy_assignment(org_id)
            return {"org_id": org_id, "assignment": assignment.__dict__ if assignment else None}
        assignments = [
            assignment.__dict__
            for assignment in (
                tenant_store.get_policy_assignment(org.org_id) for org in tenant_store.list_orgs()
            )
            if assignment
        ]
        return {"assignments": assignments}

    @app.post(
        "/admin/policy-assignments",
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_ADMIN]))],
        tags=["Admin"],
    )
    async def set_policy_assignment(req: PolicyBundleAssignRequest, request: Request):
        if policy_approval_required:
            approval = tenant_store.get_policy_approval(req.bundle_id, req.version, req.org_id)
            if approval is None:
                approval = tenant_store.get_policy_approval(req.bundle_id, req.version, None)
            if not approval or approval.status != PolicyApprovalStatus.APPROVED:
                raise HTTPException(status_code=409, detail="Policy bundle not approved")
        assignment = tenant_store.assign_policy_bundle(
            req.org_id,
            req.bundle_id,
            req.version,
            overrides=req.overrides,
        )
        actor, audit_org = _audit_actor(request)
        audit_logger.emit(
            AuditLogEntry(
                action="admin.policy_assignments.set",
                actor=actor,
                org_id=audit_org,
                target_type="policy_assignment",
                target_id=req.org_id,
                metadata=req.model_dump(),
            )
        )
        return assignment.__dict__

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

    @app.get(
        "/admin/audit-logs/export",
        dependencies=[Depends(verify_api_key), Depends(require_scopes([SCOPE_ADMIN]))],
        tags=["Admin"],
    )
    async def export_audit_logs(
        request: Request,
        format: str = "jsonl",
        org_id: Optional[str] = None,
        limit: int = 1000,
    ):
        actor, audit_org = _audit_actor(request)
        audit_logger.emit(
            AuditLogEntry(
                action="admin.audit_logs.export",
                actor=actor,
                org_id=audit_org,
                target_type="audit_log",
                metadata={"format": format, "org_id": org_id, "limit": limit},
            )
        )
        entries = _load_audit_entries(audit_path, org_id, limit=limit)
        if not entries:
            raise HTTPException(status_code=404, detail="No audit logs available")
        if format.lower() == "csv":
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(
                [
                    "timestamp",
                    "action",
                    "actor",
                    "org_id",
                    "target_type",
                    "target_id",
                    "prev_hash",
                    "hash",
                    "metadata",
                ]
            )
            for entry in entries:
                writer.writerow(
                    [
                        entry.get("timestamp"),
                        entry.get("action"),
                        entry.get("actor"),
                        entry.get("org_id"),
                        entry.get("target_type"),
                        entry.get("target_id"),
                        entry.get("prev_hash"),
                        entry.get("hash"),
                        json.dumps(entry.get("metadata", {})),
                    ]
                )
            return Response(output.getvalue(), media_type="text/csv")
        if format.lower() != "jsonl":
            raise HTTPException(status_code=400, detail="format must be jsonl or csv")
        payload = "\n".join(json.dumps(entry) for entry in entries) + "\n"
        return Response(payload, media_type="application/jsonl")

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
