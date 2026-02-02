from abc import ABC, abstractmethod
from .events import ObsEvent
import json

class EventSink(ABC):
    @abstractmethod
    def emit(self, event: ObsEvent):
        ...

class ConsoleSink(EventSink):
    def emit(self, event: ObsEvent):
        print(f"[{event.event_type}] {event.agent} :: {event.data}")

class JSONLSink(EventSink):
    def __init__(self, path: str):
        self.path = path

    def emit(self, event: ObsEvent):
        with open(self.path, "a") as f:
            f.write(json.dumps(event.__dict__) + "\n")
