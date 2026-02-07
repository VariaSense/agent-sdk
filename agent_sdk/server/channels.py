"""Channel integrations for external sources."""

from __future__ import annotations

from typing import Dict, Any, Optional

from agent_sdk.observability.stream_envelope import (
    RunMetadata,
    SessionMetadata,
    RunStatus,
    StreamEnvelope,
    StreamChannel,
)
from agent_sdk.observability.stream_envelope import new_run_id, new_session_id


async def handle_web_channel(
    runtime,
    storage,
    run_store,
    message: str,
    session_id: Optional[str] = None,
    org_id: str = "default",
) -> Dict[str, Any]:
    """Handle inbound web channel messages and return run metadata."""
    run_id = new_run_id()
    if session_id is None:
        session_id = new_session_id()
        storage.create_session(SessionMetadata(session_id=session_id, org_id=org_id))
    else:
        if storage.get_session(session_id) is None:
            storage.create_session(SessionMetadata(session_id=session_id, org_id=org_id))

    storage.create_run(
        RunMetadata(
            run_id=run_id,
            session_id=session_id,
            agent_id="planner-executor",
            org_id=org_id,
            status=RunStatus.RUNNING,
        )
    )
    run_store.create_run(run_id)

    seq = 0
    run_store.append_event(
        run_id,
        StreamEnvelope(
            run_id=run_id,
            session_id=session_id,
            stream=StreamChannel.LIFECYCLE,
            event="start",
            payload={"channel": "web", "message": message},
            status=RunStatus.RUNNING.value,
            seq=seq,
            metadata={"org_id": org_id},
        ),
    )
    seq += 1

    msgs = await runtime.run_async(message, session_id=session_id, run_id=run_id)
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
                metadata={"org_id": org_id},
            ),
        )
        seq += 1

    run_store.append_event(
        run_id,
        StreamEnvelope(
            run_id=run_id,
            session_id=session_id,
        stream=StreamChannel.LIFECYCLE,
        event="end",
        payload={"status": "completed"},
        status=RunStatus.COMPLETED.value,
        seq=seq,
        metadata={"org_id": org_id},
    ),
)

    storage.update_run(
        RunMetadata(
            run_id=run_id,
            session_id=session_id,
            agent_id="planner-executor",
            org_id=org_id,
            status=RunStatus.COMPLETED,
        )
    )

    return {
        "run_id": run_id,
        "session_id": session_id,
        "messages": [
            {
                "id": msg.id,
                "role": msg.role,
                "content": msg.content,
                "metadata": msg.metadata,
            }
            for msg in msgs
        ],
    }
