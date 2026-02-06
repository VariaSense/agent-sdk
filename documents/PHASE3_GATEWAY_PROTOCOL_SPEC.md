# Gateway Mode Protocol Spec (v0.1)

## Purpose
Define a WebSocket protocol for the Gateway mode that enables multi-client streaming, authentication, and reconnection while preserving the existing `StreamEnvelope` contract.

## Goals
- Reuse the existing `StreamEnvelope` schema for event payloads.
- Support multi-client subscriptions to run streams.
- Provide a clear auth handshake and reconnect flow.
- Keep the protocol stable and extensible.

## Non-Goals
- Multi-tenant authorization (covered in Phase 3 item 6).
- Full SaaS gateway scaling and persistence guarantees.

## Transport
- WebSocket endpoint: `GET /ws`
- Subprotocol: `agent-sdk.v1` (optional, recommended).

## Message Envelope
All gateway messages (client ↔ server) use a shared envelope:

```json
{
  "type": "auth|subscribe|unsubscribe|run|event|ack|error|ping|pong",
  "request_id": "optional-client-id",
  "timestamp": "RFC3339",
  "payload": {}
}
```

### Common Fields
- `type`: message type.
- `request_id`: optional client-provided correlation ID.
- `timestamp`: ISO 8601 / RFC3339.
- `payload`: message payload.

## Authentication

### Client → Server (Auth)
```json
{
  "type": "auth",
  "request_id": "req-123",
  "timestamp": "2026-02-06T00:00:00Z",
  "payload": {
    "api_key": "<API_KEY>",
    "client_id": "optional-client-name"
  }
}
```

### Server → Client (Ack)
```json
{
  "type": "ack",
  "request_id": "req-123",
  "timestamp": "2026-02-06T00:00:00Z",
  "payload": {
    "status": "ok"
  }
}
```

### Auth Failure
```json
{
  "type": "error",
  "request_id": "req-123",
  "timestamp": "2026-02-06T00:00:00Z",
  "payload": {
    "code": "AUTH_FAILED",
    "message": "Invalid API key"
  }
}
```

## Run Execution

### Client → Server (Run)
```json
{
  "type": "run",
  "request_id": "req-200",
  "timestamp": "2026-02-06T00:00:00Z",
  "payload": {
    "task": "Summarize this document",
    "session_id": "optional-existing-session"
  }
}
```

### Server → Client (Ack)
```json
{
  "type": "ack",
  "request_id": "req-200",
  "timestamp": "2026-02-06T00:00:00Z",
  "payload": {
    "run_id": "run_...",
    "session_id": "sess_..."
  }
}
```

## Subscriptions

### Client → Server (Subscribe)
```json
{
  "type": "subscribe",
  "request_id": "req-300",
  "timestamp": "2026-02-06T00:00:00Z",
  "payload": {
    "run_id": "run_...",
    "from_seq": 0
  }
}
```

### Server → Client (Event)
Events are streamed using `StreamEnvelope` as the payload.

```json
{
  "type": "event",
  "timestamp": "2026-02-06T00:00:00Z",
  "payload": {
    "run_id": "run_...",
    "session_id": "sess_...",
    "stream": "assistant",
    "event": "message",
    "payload": {"text": "hello"},
    "timestamp": "2026-02-06T00:00:00Z",
    "seq": 12
  }
}
```

### Client → Server (Unsubscribe)
```json
{
  "type": "unsubscribe",
  "request_id": "req-301",
  "timestamp": "2026-02-06T00:00:00Z",
  "payload": {
    "run_id": "run_..."
  }
}
```

## Reconnect Protocol
When reconnecting, clients should re-auth and resubscribe with `from_seq` set to the last received `StreamEnvelope.seq`.

```json
{
  "type": "subscribe",
  "request_id": "req-302",
  "timestamp": "2026-02-06T00:00:00Z",
  "payload": {
    "run_id": "run_...",
    "from_seq": 12
  }
}
```

Server behavior:
- If `from_seq` is provided, replay events starting at `seq >= from_seq`.
- If the run has ended and all events are complete, replay and then close the stream.

## Heartbeats
Either side may send:

```json
{"type": "ping", "timestamp": "...", "payload": {}}
```

Receiver should reply with:

```json
{"type": "pong", "timestamp": "...", "payload": {}}
```

## Error Codes
- `AUTH_FAILED`: Invalid or missing credentials.
- `RUN_NOT_FOUND`: Requested run does not exist.
- `INVALID_REQUEST`: Invalid payload or missing fields.
- `SERVER_ERROR`: Unexpected server failure.

## Backpressure
Server may throttle event delivery if client consumption is slow. The protocol does not guarantee delivery beyond the retention window on reconnect.

## Versioning
- Envelope `type` and `payload` fields are stable for `agent-sdk.v1`.
- `StreamEnvelope` payload fields should remain backward compatible.
