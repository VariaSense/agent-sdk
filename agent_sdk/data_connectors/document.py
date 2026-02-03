"""Document and chunk data models for data connectors."""

from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone


@dataclass
class Document:
    """Unified document representation for various data sources."""
    
    content: str
    """The main document content."""
    
    metadata: Dict[str, Any] = field(default_factory=dict)
    """Document metadata (title, author, source, etc)."""
    
    source: str = "unknown"
    """Source of the document (file path, URL, etc)."""
    
    doc_id: Optional[str] = None
    """Unique document identifier."""
    
    created_at: Optional[datetime] = None
    """Document creation timestamp."""
    
    def __post_init__(self):
        """Generate defaults if needed."""
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)
        if self.doc_id is None:
            # Generate simple ID from source
            self.doc_id = f"doc_{hash(self.source) & 0x7fffffff}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize document to dictionary.
        
        Returns:
            Dictionary representation of the document.
        """
        return {
            "content": self.content,
            "metadata": self.metadata,
            "source": self.source,
            "doc_id": self.doc_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
    
    def to_text(self) -> str:
        """Get document as plain text.
        
        Returns:
            Document content as text.
        """
        return self.content
    
    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get metadata value by key.
        
        Args:
            key: Metadata key to retrieve.
            default: Default value if key not found.
            
        Returns:
            Metadata value or default.
        """
        return self.metadata.get(key, default)


@dataclass
class Chunk:
    """Document chunk for embeddings and processing."""
    
    content: str
    """The chunk content."""
    
    document_id: str
    """ID of parent document."""
    
    chunk_number: int
    """Sequential chunk number within document."""
    
    metadata: Dict[str, Any] = field(default_factory=dict)
    """Chunk-specific metadata."""
    
    embedding: Optional[List[float]] = None
    """Vector embedding for the chunk."""
    
    created_at: Optional[datetime] = None
    """Chunk creation timestamp."""
    
    def __post_init__(self):
        """Generate defaults if needed."""
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)
    
    def get_chunk_id(self) -> str:
        """Get unique chunk identifier.
        
        Returns:
            Unique chunk ID combining document and chunk number.
        """
        return f"{self.document_id}_{self.chunk_number}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize chunk to dictionary.
        
        Returns:
            Dictionary representation of the chunk.
        """
        return {
            "content": self.content,
            "document_id": self.document_id,
            "chunk_number": self.chunk_number,
            "chunk_id": self.get_chunk_id(),
            "metadata": self.metadata,
            "embedding": self.embedding,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
    
    def has_embedding(self) -> bool:
        """Check if chunk has an embedding.
        
        Returns:
            True if embedding is present.
        """
        return self.embedding is not None and len(self.embedding) > 0
