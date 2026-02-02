from dataclasses import dataclass
from typing import Callable, Dict, Any, List

@dataclass
class Tool:
    name: str
    description: str
    func: Callable[[Dict[str, Any]], Any]

    def __call__(self, args: Dict[str, Any]) -> Any:
        return self.func(args)

    async def call_async(self, args: Dict[str, Any]) -> Any:
        import inspect, asyncio
        if inspect.iscoroutinefunction(self.func):
            return await self.func(args)
        return await asyncio.to_thread(self.func, args)

class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool):
        self._tools[tool.name] = tool

    @property
    def tools(self) -> Dict[str, Tool]:
        return self._tools

    def list_tools(self) -> List[Tool]:
        return list(self._tools.values())

GLOBAL_TOOL_REGISTRY = ToolRegistry()

def tool(name: str, description: str):
    def decorator(func):
        t = Tool(name=name, description=description, func=func)
        GLOBAL_TOOL_REGISTRY.register(t)
        return func
    return decorator
