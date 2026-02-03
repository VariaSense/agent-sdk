"""Extended Data Connectors: S3, Elasticsearch support."""

from typing import Any, Dict, List, Optional
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class S3Document:
    """Document from S3."""
    bucket: str
    key: str
    content: str
    metadata: Dict[str, Any]


class S3Connector:
    """Connects to S3 buckets."""

    def __init__(self, bucket_name: str):
        self.bucket_name = bucket_name

    async def list_objects(self, prefix: str = "") -> List[str]:
        """List objects in bucket."""
        # Mock implementation
        return [f"{prefix}file1.txt", f"{prefix}file2.txt"]

    async def get_object(self, key: str) -> Optional[S3Document]:
        """Get object from S3."""
        return S3Document(
            bucket=self.bucket_name,
            key=key,
            content="mock content",
            metadata={"size": 1024},
        )

    async def put_object(self, key: str, content: str) -> bool:
        """Put object to S3."""
        return True


@dataclass
class ElasticsearchResult:
    """Result from Elasticsearch."""
    doc_id: str
    score: float
    content: Dict[str, Any]


class ElasticsearchConnector:
    """Connects to Elasticsearch."""

    def __init__(self, host: str = "localhost", port: int = 9200):
        self.host = host
        self.port = port

    async def search(
        self,
        index: str,
        query: Dict[str, Any],
        limit: int = 10,
    ) -> List[ElasticsearchResult]:
        """Search documents."""
        # Mock implementation
        return [
            ElasticsearchResult(
                doc_id=f"doc_{i}",
                score=0.9 - (i * 0.1),
                content={"text": f"result {i}"},
            )
            for i in range(limit)
        ]

    async def index_document(
        self,
        index: str,
        doc_id: str,
        document: Dict[str, Any],
    ) -> bool:
        """Index a document."""
        return True
