"""Tests for run log exporters."""

import io
import json

from agent_sdk.observability.run_logs import JSONLFileExporter, StdoutExporter
from agent_sdk.observability.stream_envelope import StreamEnvelope, StreamChannel
from agent_sdk.server.run_store import RunEventStore


def _sample_event() -> StreamEnvelope:
    return StreamEnvelope(
        run_id="run_test",
        session_id="sess_test",
        stream=StreamChannel.LIFECYCLE,
        event="start",
        payload={"status": "running"},
        seq=1,
    )


def test_jsonl_file_exporter_writes_event(tmp_path):
    path = tmp_path / "run.jsonl"
    exporter = JSONLFileExporter(str(path))
    event = _sample_event()

    exporter.emit(event)

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["run_id"] == "run_test"
    assert payload["event"] == "start"


def test_stdout_exporter_writes_event():
    buffer = io.StringIO()
    exporter = StdoutExporter(stream=buffer)
    event = _sample_event()

    exporter.emit(event)

    output = buffer.getvalue().strip()
    payload = json.loads(output)
    assert payload["session_id"] == "sess_test"
    assert payload["stream"] == "lifecycle"


def test_run_store_emits_to_exporters():
    events = []

    class _Collector:
        def emit(self, event):
            events.append(event)

    store = RunEventStore(exporters=[_Collector()])
    event = _sample_event()

    store.append_event(event.run_id, event)

    assert events == [event]
