"""Tests for RunEventStore stream_from behavior."""

import asyncio
import pytest

from agent_sdk.server.run_store import RunEventStore
from agent_sdk.observability.stream_envelope import StreamEnvelope, StreamChannel


@pytest.mark.asyncio
async def test_stream_from_seq_filters_history():
    store = RunEventStore()
    run_id = "run_seq_test"
    store.create_run(run_id)
    store.append_event(
        run_id,
        StreamEnvelope(
            run_id=run_id,
            session_id="sess_1",
            stream=StreamChannel.LIFECYCLE,
            event="start",
            payload={"task": "hi"},
            seq=0,
        ),
    )
    store.append_event(
        run_id,
        StreamEnvelope(
            run_id=run_id,
            session_id="sess_1",
            stream=StreamChannel.LIFECYCLE,
            event="end",
            payload={"status": "done"},
            seq=1,
        ),
    )

    events = []
    async for event in store.stream_from(run_id, from_seq=1):
        events.append(event)
    assert len(events) == 1
    assert events[0].seq == 1
