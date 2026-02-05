from importlib.metadata import entry_points
from agent_sdk.core.tools import GLOBAL_TOOL_REGISTRY
from agent_sdk.core.agent import Agent
from agent_sdk.llm.base import LLMClient

class PluginLoader:
    def __init__(self):
        self.tools = {}
        self.agents = {}
        self.llms = {}

    def _iter_eps(self, eps, group: str):
        if hasattr(eps, "select"):
            return eps.select(group=group)
        return eps.get(group, [])

    def load(self):
        eps = entry_points()

        for ep in self._iter_eps(eps, "agent_sdk.tools"):
            func = ep.load()
            func(GLOBAL_TOOL_REGISTRY)
            self.tools[ep.name] = func

        for ep in self._iter_eps(eps, "agent_sdk.agents"):
            cls = ep.load()
            if issubclass(cls, Agent):
                self.agents[ep.name] = cls

        for ep in self._iter_eps(eps, "agent_sdk.llm"):
            cls = ep.load()
            if issubclass(cls, LLMClient):
                self.llms[ep.name] = cls
