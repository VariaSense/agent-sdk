"""Core runtime support ports."""

from __future__ import annotations

from typing import Any, Iterable, Optional, Protocol, runtime_checkable


@runtime_checkable
class EventPublisherPort(Protocol):
    def emit(self, event: Any) -> None:
        ...


@runtime_checkable
class ToolRegistryPort(Protocol):
    def get(self, name: str) -> Any:
        ...

    def values(self) -> Iterable[Any]:
        ...


@runtime_checkable
class MemoryRepositoryPort(Protocol):
    def add_short_term_message(self, message: Any) -> None:
        ...

    def add_long_term_message(self, message: Any) -> None:
        ...

    def cleanup_old_messages(self, keep_count: Optional[int] = None) -> None:
        ...
