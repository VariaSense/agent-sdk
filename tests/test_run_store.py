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


def test_run_store_replay_then_stop_on_end():
    store = RunEventStore()
    run_id = "run_replay"
    store.create_run(run_id)
    store.append_event(run_id, StreamEnvelope(run_id=run_id, session_id="sess", stream=StreamChannel.LIFECYCLE, event="start", payload={}))
    store.append_event(run_id, StreamEnvelope(run_id=run_id, session_id="sess", stream=StreamChannel.LIFECYCLE, event="end", payload={}))

    async def collect():
        collected = []
        async for event in store.stream(run_id):
            collected.append(event)
        return collected

    collected_events = asyncio.run(collect())
    assert [e.event for e in collected_events] == ["start", "end"]


def test_run_store_disconnect_allows_future_replay():
    store = RunEventStore()
    run_id = "run_disconnect"
    store.create_run(run_id)
    store.append_event(run_id, StreamEnvelope(run_id=run_id, session_id="sess", stream=StreamChannel.LIFECYCLE, event="start", payload={}))

    async def disconnect_after_first():
        gen = store.stream(run_id)
        first = await gen.__anext__()
        await gen.aclose()
        return first

    first_event = asyncio.run(disconnect_after_first())
    assert first_event.event == "start"

    store.append_event(run_id, StreamEnvelope(run_id=run_id, session_id="sess", stream=StreamChannel.ASSISTANT, event="message", payload={"text": "hi"}))
    store.append_event(run_id, StreamEnvelope(run_id=run_id, session_id="sess", stream=StreamChannel.LIFECYCLE, event="end", payload={}))

    async def collect_again():
        collected = []
        async for event in store.stream(run_id):
            collected.append(event)
        return collected

    collected_events = asyncio.run(collect_again())
    assert [e.event for e in collected_events] == ["start", "message", "end"]
