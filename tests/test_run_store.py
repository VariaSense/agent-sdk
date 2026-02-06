"""
Regression tests for run event ordering.
"""

import asyncio

from agent_sdk.observability.stream_envelope import StreamEnvelope, StreamChannel
from agent_sdk.server.run_store import RunEventStore


def test_run_store_event_ordering():
    store = RunEventStore()
    run_id = "run_ordered"
    store.create_run(run_id)

    events = [
        StreamEnvelope(run_id=run_id, session_id="sess", stream=StreamChannel.LIFECYCLE, event="start", payload={}),
        StreamEnvelope(run_id=run_id, session_id="sess", stream=StreamChannel.ASSISTANT, event="message", payload={"text": "hi"}),
        StreamEnvelope(run_id=run_id, session_id="sess", stream=StreamChannel.LIFECYCLE, event="end", payload={}),
    ]

    for event in events:
        store.append_event(run_id, event)

    async def collect():
        collected = []
        async for event in store.stream(run_id):
            collected.append(event)
        return collected

    collected_events = asyncio.run(collect())
    assert [e.event for e in collected_events] == ["start", "message", "end"]
