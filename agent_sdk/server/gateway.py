"""Gateway WebSocket server implementation."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import WebSocket, WebSocketDisconnect

from agent_sdk.observability.stream_envelope import (
    StreamEnvelope,
    StreamChannel,
    RunStatus,
    RunMetadata,
    SessionMetadata,
    new_run_id,
    new_session_id,
)
from agent_sdk.server.run_store import RunEventStore
from agent_sdk.security import APIKeyManager

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class GatewayEnvelope:
    type: str
    request_id: Optional[str]
    timestamp: str
    payload: Dict[str, Any]

    @classmethod
    def from_json(cls, raw: str) -> "GatewayEnvelope":
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid JSON") from exc
        message_type = data.get("type")
        if not message_type:
            raise ValueError("Missing type")
        return cls(
            type=message_type,
            request_id=data.get("request_id"),
            timestamp=data.get("timestamp") or _now_iso(),
            payload=data.get("payload") or {},
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "request_id": self.request_id,
            "timestamp": self.timestamp,
            "payload": self.payload,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


class GatewayConnection:
    def __init__(self, websocket: WebSocket, client_id: str, send_queue_size: int = 100):
        self.websocket = websocket
        self.client_id = client_id
        self.queue: asyncio.Queue[GatewayEnvelope] = asyncio.Queue(maxsize=send_queue_size)
        self.subscriptions: Dict[str, asyncio.Task] = {}
        self.authenticated = False

    def enqueue(self, envelope: GatewayEnvelope) -> bool:
        try:
            self.queue.put_nowait(envelope)
            return True
        except asyncio.QueueFull:
            try:
                self.queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            try:
                self.queue.put_nowait(envelope)
                return False
            except asyncio.QueueFull:
                return False

    async def send_loop(self) -> None:
        while True:
            envelope = await self.queue.get()
            await self.websocket.send_text(envelope.to_json())


class GatewayServer:
    def __init__(
        self,
        runtime,
        run_store: RunEventStore,
        storage,
        api_key_manager: APIKeyManager,
        send_queue_size: int = 100,
        tenant_store=None,
        default_org_id: str = "default",
    ):
        self.runtime = runtime
        self.run_store = run_store
        self.storage = storage
        self.api_key_manager = api_key_manager
        self.send_queue_size = send_queue_size
        self.tenant_store = tenant_store
        self.default_org_id = default_org_id
        self.connections: Dict[str, GatewayConnection] = {}

    async def handle_connection(self, websocket: WebSocket) -> None:
        await websocket.accept()
        client_id = f"ws_{uuid.uuid4().hex}"
        connection = GatewayConnection(websocket, client_id, self.send_queue_size)
        self.connections[client_id] = connection
        send_task = asyncio.create_task(connection.send_loop())
        try:
            await self._auth_handshake(connection)
            async for message in websocket.iter_text():
                await self._handle_message(connection, message)
        except WebSocketDisconnect:
            pass
        finally:
            for task in connection.subscriptions.values():
                task.cancel()
            send_task.cancel()
            self.connections.pop(client_id, None)

    async def _auth_handshake(self, connection: GatewayConnection) -> None:
        raw = await connection.websocket.receive_text()
        try:
            envelope = GatewayEnvelope.from_json(raw)
        except ValueError as exc:
            await self._send_error(connection, "INVALID_REQUEST", str(exc), None)
            return
        if envelope.type != "auth":
            await self._send_error(connection, "AUTH_REQUIRED", "Auth required", envelope.request_id)
            return
        api_key = envelope.payload.get("api_key")
        if not api_key or not self.api_key_manager.verify_key(api_key):
            await self._send_error(connection, "AUTH_FAILED", "Invalid API key", envelope.request_id)
            return
        connection.authenticated = True
        connection.enqueue(
            GatewayEnvelope(
                type="ack",
                request_id=envelope.request_id,
                timestamp=_now_iso(),
                payload={"status": "ok"},
            )
        )

    async def _handle_message(self, connection: GatewayConnection, raw: str) -> None:
        try:
            envelope = GatewayEnvelope.from_json(raw)
        except ValueError as exc:
            await self._send_error(connection, "INVALID_REQUEST", str(exc), None)
            return
        if not connection.authenticated and envelope.type != "auth":
            await self._send_error(connection, "AUTH_REQUIRED", "Auth required", envelope.request_id)
            return
        if envelope.type == "auth":
            await self._send_ack(connection, envelope.request_id, {"status": "ok"})
            return
        if envelope.type == "ping":
            connection.enqueue(
                GatewayEnvelope(
                    type="pong",
                    request_id=envelope.request_id,
                    timestamp=_now_iso(),
                    payload={},
                )
            )
            return
        if envelope.type == "run":
            await self._handle_run(connection, envelope)
            return
        if envelope.type == "subscribe":
            await self._handle_subscribe(connection, envelope)
            return
        if envelope.type == "unsubscribe":
            await self._handle_unsubscribe(connection, envelope)
            return
        await self._send_error(connection, "INVALID_REQUEST", "Unknown message type", envelope.request_id)

    async def _handle_run(self, connection: GatewayConnection, envelope: GatewayEnvelope) -> None:
        task = envelope.payload.get("task")
        if not task:
            await self._send_error(connection, "INVALID_REQUEST", "Missing task", envelope.request_id)
            return
        session_id = envelope.payload.get("session_id")
        run_id, session_id = await self._start_run(task, session_id)
        await self._send_ack(
            connection,
            envelope.request_id,
            {"run_id": run_id, "session_id": session_id},
        )

    async def _handle_subscribe(self, connection: GatewayConnection, envelope: GatewayEnvelope) -> None:
        run_id = envelope.payload.get("run_id")
        if not run_id:
            await self._send_error(connection, "INVALID_REQUEST", "Missing run_id", envelope.request_id)
            return
        if not self.run_store.has_run(run_id):
            await self._send_error(connection, "RUN_NOT_FOUND", "Run not found", envelope.request_id)
            return
        from_seq = envelope.payload.get("from_seq")
        if run_id in connection.subscriptions:
            connection.subscriptions[run_id].cancel()
        await self._send_ack(connection, envelope.request_id, {"status": "subscribed"})
        connection.subscriptions[run_id] = asyncio.create_task(
            self._stream_run(connection, run_id, from_seq)
        )

    async def _handle_unsubscribe(self, connection: GatewayConnection, envelope: GatewayEnvelope) -> None:
        run_id = envelope.payload.get("run_id")
        if not run_id:
            await self._send_error(connection, "INVALID_REQUEST", "Missing run_id", envelope.request_id)
            return
        task = connection.subscriptions.pop(run_id, None)
        if task:
            task.cancel()
        await self._send_ack(connection, envelope.request_id, {"status": "unsubscribed"})

    async def _stream_run(
        self,
        connection: GatewayConnection,
        run_id: str,
        from_seq: Optional[int] = None,
    ) -> None:
        try:
            async for event in self.run_store.stream_from(run_id, from_seq):
                connection.enqueue(
                    GatewayEnvelope(
                        type="event",
                        request_id=None,
                        timestamp=_now_iso(),
                        payload=event.to_dict(),
                    )
                )
        except Exception as exc:
            logger.error("Gateway stream error: %s", exc)
            await self._send_error(connection, "SERVER_ERROR", "Stream failure", None)

    async def _start_run(self, task: str, session_id: Optional[str]) -> tuple[str, str]:
        run_id = new_run_id()
        if session_id is None:
            session_id = new_session_id()
            self.storage.create_session(
                SessionMetadata(session_id=session_id, org_id=self.default_org_id)
            )
            if self.tenant_store is not None:
                self.tenant_store.record_session(self.default_org_id)
        else:
            if self.storage.get_session(session_id) is None:
                self.storage.create_session(
                    SessionMetadata(session_id=session_id, org_id=self.default_org_id)
                )
        self.storage.create_run(
            RunMetadata(
                run_id=run_id,
                session_id=session_id,
                agent_id="planner-executor",
                org_id=self.default_org_id,
                status=RunStatus.RUNNING,
            )
        )
        if self.tenant_store is not None:
            self.tenant_store.record_run(self.default_org_id)
        self.run_store.create_run(run_id)
        asyncio.create_task(self._emit_run_events(run_id, session_id, task))
        return run_id, session_id

    async def _emit_run_events(self, run_id: str, session_id: str, task: str) -> None:
        seq = 0
        try:
            start_event = StreamEnvelope(
                run_id=run_id,
                session_id=session_id,
                stream=StreamChannel.LIFECYCLE,
                event="start",
                payload={"task": task},
                status=RunStatus.RUNNING.value,
                seq=seq,
                metadata={"org_id": self.default_org_id},
            )
            self.run_store.append_event(run_id, start_event)
            seq += 1

            msgs = await self.runtime.run_async(task, session_id=session_id, run_id=run_id)
            for msg in msgs:
                self.run_store.append_event(
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
                        metadata={"org_id": self.default_org_id},
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
                metadata={"org_id": self.default_org_id},
            )
            self.run_store.append_event(run_id, end_event)
            self.storage.update_run(
                RunMetadata(
                    run_id=run_id,
                    session_id=session_id,
                    agent_id="planner-executor",
                    org_id=self.default_org_id,
                    status=RunStatus.COMPLETED,
                )
            )
        except Exception as exc:
            logger.error("Gateway run failed: %s", exc, exc_info=True)
            self.run_store.append_event(
                run_id,
                StreamEnvelope(
                    run_id=run_id,
                    session_id=session_id,
                    stream=StreamChannel.LIFECYCLE,
                    event="error",
                    payload={"error": str(exc)},
                    status=RunStatus.ERROR.value,
                    seq=seq,
                    metadata={"org_id": self.default_org_id},
                ),
            )
            self.storage.update_run(
                RunMetadata(
                    run_id=run_id,
                    session_id=session_id,
                    agent_id="planner-executor",
                    org_id=self.default_org_id,
                    status=RunStatus.ERROR,
                )
            )

    async def _send_ack(self, connection: GatewayConnection, request_id: Optional[str], payload: Dict[str, Any]) -> None:
        connection.enqueue(
            GatewayEnvelope(type="ack", request_id=request_id, timestamp=_now_iso(), payload=payload)
        )

    async def _send_error(
        self,
        connection: GatewayConnection,
        code: str,
        message: str,
        request_id: Optional[str],
    ) -> None:
        connection.enqueue(
            GatewayEnvelope(
                type="error",
                request_id=request_id,
                timestamp=_now_iso(),
                payload={"code": code, "message": message},
            )
        )
