import logging
import asyncio
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import ValidationError
from agent_sdk.config.loader import load_config
from agent_sdk.core.runtime import PlannerExecutorRuntime
from agent_sdk.llm.mock import MockLLMClient
from agent_sdk.plugins.loader import PluginLoader
from agent_sdk.security import verify_api_key
from agent_sdk.validators import RunTaskRequest, TaskResponse, HealthResponse, ReadyResponse
from agent_sdk.exceptions import ConfigError, AgentSDKException
from agent_sdk.observability.stream_envelope import (
    StreamEnvelope,
    StreamChannel,
    RunStatus,
    new_run_id,
    new_session_id,
)
from agent_sdk.server.run_store import RunEventStore

logger = logging.getLogger(__name__)


def create_app(config_path: str = "config.yaml"):
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
        run_store = RunEventStore()
        logger.info("Application initialized successfully")
    except ConfigError as e:
        logger.error(f"Failed to initialize application: {e}")
        # Create a minimal app that reports the error
        app = FastAPI(title="Agent SDK", version="0.1.0")
        
        @app.get("/health")
        async def health_error():
            return {"status": "unhealthy", "error": str(e)}
        
        return app

    app = FastAPI(
        title="Agent SDK",
        version="0.1.0",
        description="Agent SDK - Modular Agent Framework with Planning, Execution, and Observability"
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure properly in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.run_store = run_store

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
                detail=f"Service not ready: {str(e)}"
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
            msgs = await runtime.run_async(req.task)
            
            result_data = {
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
            raise HTTPException(status_code=400, detail=f"Invalid input: {str(e)}")
        except AgentSDKException as e:
            logger.error(f"Agent SDK error: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Task execution failed: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Unexpected error during task execution: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail="Internal server error"
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
