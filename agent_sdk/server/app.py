import logging
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import ValidationError
from agent_sdk.config.loader import load_config
from agent_sdk.core.runtime import PlannerExecutorRuntime
from agent_sdk.core.streaming import StreamingAgent, StreamEventCollector, StreamEventType
from agent_sdk.llm.mock import MockLLMClient
from agent_sdk.plugins.loader import PluginLoader
from agent_sdk.security import verify_api_key
from agent_sdk.validators import RunTaskRequest, TaskResponse, HealthResponse, ReadyResponse
from agent_sdk.exceptions import ConfigError, AgentSDKException

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
        async def event_generator():
            try:
                logger.info(f"Starting streaming task execution: {req.task[:100]}")
                
                # Create event collector for streaming
                event_collector = StreamEventCollector()
                
                # Emit start event
                event_collector.add_agent_start(
                    agent_id="agent-0",
                    goal=req.task
                )
                yield event_collector.events[-1].to_sse_format()
                
                # Execute the task and emit events
                msgs = await runtime.run_async(req.task)
                
                # Emit plan event
                event_collector.add_plan_event(
                    f"Executed {len(msgs)} steps"
                )
                yield event_collector.events[-1].to_sse_format()
                
                # Emit message events
                for i, msg in enumerate(msgs):
                    event_collector.add_step_complete(
                        step_id=f"step-{i}",
                        result=msg.content[:200]
                    )
                    yield event_collector.events[-1].to_sse_format()
                
                # Emit completion event
                event_collector.add_agent_complete(
                    agent_id="agent-0",
                    final_result=f"Completed with {len(msgs)} messages"
                )
                yield event_collector.events[-1].to_sse_format()
                
                logger.info("Streaming task execution completed successfully")
                
            except Exception as e:
                logger.error(f"Error during streaming execution: {e}", exc_info=True)
                event_collector.add_error(str(e))
                yield event_collector.events[-1].to_sse_format()
        
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
