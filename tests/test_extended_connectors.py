"""Tests for Extended Data Connectors."""
import pytest
from agent_sdk.data_connectors.extended_connectors import (
    S3Connector, ElasticsearchConnector, S3Document, ElasticsearchResult,
)


class TestS3Connector:
    @pytest.mark.asyncio
    async def test_list_objects(self):
        connector = S3Connector("test-bucket")
        objects = await connector.list_objects()
        assert len(objects) > 0

    @pytest.mark.asyncio
    async def test_get_object(self):
        connector = S3Connector("test-bucket")
        doc = await connector.get_object("test.txt")
        assert doc is not None
        assert doc.key == "test.txt"

    @pytest.mark.asyncio
    async def test_put_object(self):
        connector = S3Connector("test-bucket")
        result = await connector.put_object("test.txt", "content")
        assert result is True


class TestElasticsearchConnector:
    @pytest.mark.asyncio
    async def test_search(self):
        connector = ElasticsearchConnector()
        results = await connector.search(
            "test-index",
            {"query": "test"},
            limit=5,
        )
        assert len(results) == 5
        assert all(isinstance(r, ElasticsearchResult) for r in results)

    @pytest.mark.asyncio
    async def test_index_document(self):
        connector = ElasticsearchConnector()
        result = await connector.index_document(
            "test-index",
            "doc1",
            {"text": "content"},
        )
        assert result is True
