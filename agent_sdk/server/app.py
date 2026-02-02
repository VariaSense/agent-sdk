from fastapi import FastAPI
from pydantic import BaseModel
from agent_sdk.config.loader import load_config
from agent_sdk.core.runtime import PlannerExecutorRuntime
from agent_sdk.llm.mock import MockLLMClient
from agent_sdk.plugins.loader import PluginLoader

class TaskRequest(BaseModel):
    task: str

def create_app(config_path: str = "config.yaml"):
    loader = PluginLoader()
    loader.load()
    planner, executor = load_config(config_path, MockLLMClient())
    runtime = PlannerExecutorRuntime(planner, executor)

    app = FastAPI()

    @app.post("/run")
    async def run_task(req: TaskRequest):
        msgs = await runtime.run_async(req.task)
        return {"messages": [m.__dict__ for m in msgs]}

    return app
