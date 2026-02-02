from typing import List
from .events import ObsEvent
from .sinks import EventSink

class EventBus:
    def __init__(self, sinks: List[EventSink] | None = None):
        self.sinks = sinks or []

    def add_sink(self, sink: EventSink):
        self.sinks.append(sink)

    def emit(self, event: ObsEvent):
        for s in self.sinks:
            s.emit(event)
