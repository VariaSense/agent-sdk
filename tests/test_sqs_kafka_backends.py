"""Tests for SQS and Kafka queue backends with fake clients."""

from types import SimpleNamespace

from agent_sdk.execution.durable_queue import SQSQueueBackend, KafkaQueueBackend


class FakeSQS:
    def __init__(self):
        self.messages = []

    def send_message(self, QueueUrl, MessageBody):
        message_id = f"msg-{len(self.messages)}"
        self.messages.append({"MessageId": message_id, "Body": MessageBody, "ReceiptHandle": message_id})
        return {"MessageId": message_id}

    def receive_message(self, QueueUrl, MaxNumberOfMessages=1, WaitTimeSeconds=0):
        if not self.messages:
            return {"Messages": []}
        msg = self.messages.pop(0)
        return {"Messages": [msg]}

    def delete_message(self, QueueUrl, ReceiptHandle):
        return {}


def test_sqs_queue_backend_roundtrip():
    client = FakeSQS()
    backend = SQSQueueBackend(queue_url="queue-url", client=client)
    backend.enqueue({"task": "ping"}, max_attempts=2)
    job = backend.claim_next()
    assert job is not None
    assert job.payload["task"] == "ping"


class FakeKafkaProducer:
    def __init__(self, store):
        self.store = store

    def send(self, topic, value):
        self.store.append(SimpleNamespace(value=value))


class FakeKafkaConsumer:
    def __init__(self, store):
        self.store = store

    def poll(self, timeout_ms=0):
        if not self.store:
            return {}
        return {0: [self.store.pop(0)]}


def test_kafka_queue_backend_roundtrip():
    store = []
    backend = KafkaQueueBackend(
        "agent-sdk-jobs",
        client={"producer": FakeKafkaProducer(store), "consumer": FakeKafkaConsumer(store)},
    )
    backend.enqueue({"task": "ping"}, max_attempts=2)
    job = backend.claim_next()
    assert job is not None
    assert job.payload["task"] == "ping"
