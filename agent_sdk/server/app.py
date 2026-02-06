import logging
import asyncio
import os
from dataclasses import asdict
from typing import Optional
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.responses import StreamingResponse
from pydantic import ValidationError
from agent_sdk.config.loader import load_config
from agent_sdk.core.runtime import PlannerExecutorRuntime
from agent_sdk.llm.mock import MockLLMClient
from agent_sdk.plugins.loader import PluginLoader
from agent_sdk.security import verify_api_key, get_api_key_manager
from agent_sdk.validators import RunTaskRequest, TaskResponse, HealthResponse, ReadyResponse
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
from agent_sdk.server.run_store import RunEventStore
from agent_sdk.storage.sqlite import SQLiteStorage

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
        log_path = os.getenv("AGENT_SDK_RUN_LOG_PATH")
        log_stdout = os.getenv("AGENT_SDK_RUN_LOG_STDOUT", "").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        run_store = RunEventStore(
            exporters=create_run_log_exporters(
                path=log_path,
                emit_stdout=log_stdout,
            )
        )
        db_path = storage_path or os.getenv("AGENT_SDK_DB_PATH", "agent_sdk.db")
        storage = SQLiteStorage(db_path)
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

    ui_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ui"))
    ui_source = os.path.join(ui_root, "index.html")
    ui_dist = os.path.join(ui_root, "dist", "index.html")

    def _resolve_ui_path() -> str:
        if os.path.exists(ui_dist):
            return ui_dist
        return ui_source

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
    public_paths = ("/health", "/ready", "/docs", "/openapi.json", "/redoc")

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

    app.state.run_store = run_store
    app.state.storage = storage

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

    # Task Execution Endpoint
    @app.post(
        "/run",
        response_model=TaskResponse,
        dependencies=[Depends(verify_api_key)],
        tags=["Tasks"]
    )
    async def run_task(req: RunTaskRequest):
        """Execute a task using the planner-executor runtime
        
        Args:
            req: Task execution request with task description and optional config
            
        Returns:
            Task execution result with status and messages
        """
        try:
            logger.info(f"Executing task: {req.task[:100]}")
            session_id = new_session_id()
            run_id = new_run_id()

            session = SessionMetadata(session_id=session_id)
            storage.create_session(session)

            run_meta = RunMetadata(
                run_id=run_id,
                session_id=session_id,
                agent_id="planner-executor",
                status=RunStatus.RUNNING,
            )
            storage.create_run(run_meta)

            msgs = await runtime.run_async(req.task, session_id=session_id, run_id=run_id)
            run_meta = RunMetadata(
                run_id=run_id,
                session_id=session_id,
                agent_id="planner-executor",
                status=RunStatus.COMPLETED,
            )
            storage.update_run(run_meta)
            
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
            return TaskResponse(
                status="success",
                result=result_data,
                execution_time_ms=0
            )
        except ValidationError as e:
            logger.warning(f"Validation error: {e}")
            raise HTTPException(
                status_code=400,
                detail=_hinted_detail(
                    f"Invalid input: {str(e)}",
                    "Check required fields and types in the request payload.",
                ),
            )
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
        dependencies=[Depends(verify_api_key)],
        tags=["Tasks"]
    )
    async def run_task_stream(req: RunTaskRequest):
        """Execute a task and stream events in real-time
        
        Args:
            req: Task execution request
            
        Returns:
            Server-Sent Events stream with execution events
        """
        async def emit_run_events(run_id: str, session_id: str) -> None:
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
                )
                run_store.append_event(run_id, start_event)
                seq += 1

                msgs = await runtime.run_async(req.task, session_id=session_id, run_id=run_id)
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
                )
                run_store.append_event(run_id, end_event)
                storage.update_run(
                    RunMetadata(
                        run_id=run_id,
                        session_id=session_id,
                        agent_id="planner-executor",
                        status=RunStatus.COMPLETED,
                    )
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
                    ),
                )
                storage.update_run(
                    RunMetadata(
                        run_id=run_id,
                        session_id=session_id,
                        agent_id="planner-executor",
                        status=RunStatus.ERROR,
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

        run_id = new_run_id()
        session_id = new_session_id()
        storage.create_session(SessionMetadata(session_id=session_id))
        storage.create_run(
            RunMetadata(
                run_id=run_id,
                session_id=session_id,
                agent_id="planner-executor",
                status=RunStatus.RUNNING,
            )
        )
        run_store.create_run(run_id)
        asyncio.create_task(emit_run_events(run_id, session_id))

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
        dependencies=[Depends(verify_api_key)],
        tags=["Tasks"]
    )
    async def stream_run_events(run_id: str):
        """Stream events for a given run id."""
        if not run_store.has_run(run_id):
            raise HTTPException(status_code=404, detail="Run not found")

        async def event_generator():
            async for event in run_store.stream(run_id):
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
        "/run/{run_id}",
        dependencies=[Depends(verify_api_key)],
        tags=["Tasks"]
    )
    async def get_run(run_id: str):
        run = storage.get_run(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        data = asdict(run)
        data["status"] = run.status.value
        return data

    @app.get(
        "/sessions",
        dependencies=[Depends(verify_api_key)],
        tags=["Tasks"]
    )
    async def list_sessions(limit: int = 100):
        sessions = storage.list_sessions(limit=limit)
        return [asdict(session) for session in sessions]

    @app.get(
        "/sessions/{session_id}",
        dependencies=[Depends(verify_api_key)],
        tags=["Tasks"]
    )
    async def get_session(session_id: str):
        session = storage.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        return asdict(session)

    # List Tools Endpoint
    @app.get("/tools", tags=["Tools"])
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
