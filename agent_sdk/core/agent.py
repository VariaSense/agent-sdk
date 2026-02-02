from abc import ABC, abstractmethod
from .messages import Message

class Agent(ABC):
    def __init__(self, name: str, context: "AgentContext"):
        self.name = name
        self.context = context

    @abstractmethod
    def step(self, incoming: Message) -> Message:
        ...

    async def step_async(self, incoming: Message) -> Message:
        import asyncio
        return await asyncio.to_thread(self.step, incoming)
