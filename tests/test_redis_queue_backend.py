"""Tests for Redis queue backend using a fake client."""

from agent_sdk.execution.durable_queue import RedisQueueBackend


class FakeRedis:
    def __init__(self):
        self.hashes = {}
        self.lists = {}

    def hset(self, key, mapping):
        self.hashes.setdefault(key, {}).update(mapping)

    def hget(self, key, field):
        value = self.hashes.get(key, {}).get(field)
        if value is None:
            return None
        if isinstance(value, str):
            return value.encode("utf-8")
        return value

    def lpush(self, key, value):
        self.lists.setdefault(key, []).insert(0, value)

    def rpop(self, key):
        values = self.lists.get(key, [])
        if not values:
            return None
        return values.pop()

    def delete(self, key):
        self.hashes.pop(key, None)


def test_redis_queue_backend_enqueue_and_claim():
    client = FakeRedis()
    backend = RedisQueueBackend(url="redis://unused", client=client)
    job_id = backend.enqueue({"task": "ping"}, max_attempts=2)
    job = backend.claim_next()
    assert job is not None
    assert job.job_id == job_id
    assert job.payload["task"] == "ping"
