"""Tests for persistence layer."""

import pytest
import os
import json
import tempfile
from agent_sdk.data_connectors.document import Document
from agent_sdk.memory.persistence import (
    MemoryStore,
    FileSystemStore,
    SQLiteVectorStore,
    PostgresVectorStore,
    PineconeStore,
)


@pytest.fixture
def sample_document():
    """Create a sample document."""
    return Document(
        content="Test document content",
        metadata={"key": "value", "index": 1},
        source="test_source"
    )


@pytest.fixture
def sample_embedding():
    """Create a sample embedding."""
    return [0.1, 0.2, 0.3, 0.4, 0.5] * 10  # 50-dimensional vector


@pytest.fixture
def temp_dir():
    """Create temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


class TestFileSystemStore:
    """Tests for filesystem persistence."""
    
    def test_filesystem_store_creation(self, temp_dir):
        """Test creating filesystem store."""
        store = FileSystemStore(base_dir=temp_dir)
        
        assert store is not None
        assert store.base_dir == temp_dir
        assert os.path.exists(store.documents_dir)
        assert os.path.exists(store.embeddings_dir)
    
    def test_filesystem_store_default_dir(self):
        """Test filesystem store with default directory."""
        store = FileSystemStore()
        
        assert store.base_dir == "./vector_store"
    
    def test_filesystem_store_paths(self, temp_dir, sample_document):
        """Test path generation."""
        store = FileSystemStore(base_dir=temp_dir)
        
        doc_path = store._get_doc_path(sample_document.doc_id)
        emb_path = store._get_embedding_path(sample_document.doc_id)
        
        assert doc_path.endswith('.json')
        assert emb_path.endswith('.pkl')
    
    @pytest.mark.asyncio
    async def test_filesystem_save_load(self, temp_dir, sample_document, sample_embedding):
        """Test save and load operations."""
        store = FileSystemStore(base_dir=temp_dir)
        
        # Save
        await store.save(sample_document, sample_embedding)
        
        # Verify files exist
        doc_path = store._get_doc_path(sample_document.doc_id)
        emb_path = store._get_embedding_path(sample_document.doc_id)
        
        assert os.path.exists(doc_path)
        assert os.path.exists(emb_path)
        
        # Load
        result = await store.load(sample_document.doc_id)
        
        assert result is not None
        loaded_doc, loaded_emb = result
        
        assert loaded_doc.content == sample_document.content
        assert loaded_doc.source == sample_document.source
        assert loaded_emb == sample_embedding
    
    @pytest.mark.asyncio
    async def test_filesystem_load_nonexistent(self, temp_dir):
        """Test loading nonexistent document."""
        store = FileSystemStore(base_dir=temp_dir)
        
        result = await store.load("nonexistent_id")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_filesystem_delete(self, temp_dir, sample_document, sample_embedding):
        """Test delete operation."""
        store = FileSystemStore(base_dir=temp_dir)
        
        # Save
        await store.save(sample_document, sample_embedding)
        
        # Delete
        deleted = await store.delete(sample_document.doc_id)
        
        assert deleted
        
        # Verify deleted
        result = await store.load(sample_document.doc_id)
        assert result is None
    
    @pytest.mark.asyncio
    async def test_filesystem_list_all(self, temp_dir, sample_embedding):
        """Test listing all documents."""
        store = FileSystemStore(base_dir=temp_dir)
        
        # Create multiple documents with explicit IDs to avoid collisions
        docs = [
            Document(
                content=f"Doc {i}",
                source="test",
                doc_id=f"doc_{i}"
            )
            for i in range(3)
        ]
        
        for doc in docs:
            await store.save(doc, sample_embedding)
        
        # List
        doc_ids = await store.list_all()
        
        assert len(doc_ids) == 3
        assert all(doc.doc_id in doc_ids for doc in docs)
        assert doc_ids == sorted(doc_ids)  # Should be sorted


class TestMemoryStore:
    """Tests for MemoryStore abstract base class."""
    
    def test_memory_store_is_abstract(self):
        """Test that MemoryStore cannot be instantiated."""
        with pytest.raises(TypeError):
            MemoryStore()
    
    def test_memory_store_subclass_requirement(self):
        """Test that subclasses must implement abstract methods."""
        class IncompleteStore(MemoryStore):
            async def save(self, document, embedding):
                pass
        
        # Should still raise because not all methods implemented
        with pytest.raises(TypeError):
            IncompleteStore()


class TestPostgresVectorStore:
    """Tests for PostgreSQL vector store."""
    
    def test_postgres_store_creation(self):
        """Test creating PostgreSQL store."""
        try:
            store = PostgresVectorStore(
                connection_string="postgresql://user:pass@localhost/db",
                table_name="vectors"
            )
            
            assert store is not None
            assert store.table_name == "vectors"
        except ImportError:
            pytest.skip("psycopg2 not installed")
    
    def test_postgres_store_requires_psycopg2(self):
        """Test that PostgreSQL store requires psycopg2."""
        try:
            import psycopg2  # Check if available
            # If available, skip this test
            pytest.skip("psycopg2 is available")
        except ImportError:
            # Expected - should raise when creating store
            with pytest.raises(ImportError):
                PostgresVectorStore(
                    connection_string="postgresql://localhost/db"
                )


class TestSQLiteVectorStore:
    """Tests for SQLite vector store."""

    @pytest.mark.asyncio
    async def test_sqlite_save_load_delete(self, tmp_path, sample_document, sample_embedding):
        db_path = tmp_path / "vectors.db"
        store = SQLiteVectorStore(path=str(db_path))

        await store.save(sample_document, sample_embedding)
        loaded = await store.load(sample_document.doc_id)
        assert loaded is not None
        loaded_doc, loaded_embedding = loaded
        assert loaded_doc.content == sample_document.content
        assert loaded_embedding == sample_embedding

        doc_ids = await store.list_all()
        assert doc_ids == [sample_document.doc_id]

        deleted = await store.delete(sample_document.doc_id)
        assert deleted is True
        assert await store.load(sample_document.doc_id) is None


class TestPineconeStore:
    """Tests for Pinecone vector store."""
    
    def test_pinecone_store_creation(self):
        """Test creating Pinecone store."""
        try:
            # Try to import pinecone
            import pinecone
            pytest.skip("pinecone is available, skipping mock test")
        except ImportError:
            # Expected
            with pytest.raises(ImportError):
                PineconeStore(
                    api_key="test-key",
                    index_name="test-index"
                )
    
    def test_pinecone_store_requires_pinecone(self):
        """Test that Pinecone store requires pinecone-client."""
        try:
            store = PineconeStore(
                api_key="test-key",
                index_name="test"
            )
            pytest.skip("pinecone is installed")
        except ImportError:
            # Expected
            pass


class TestPersistenceWithDocuments:
    """Tests for persistence with real documents."""
    
    @pytest.mark.asyncio
    async def test_save_multiple_documents(self, temp_dir):
        """Test saving multiple documents."""
        store = FileSystemStore(base_dir=temp_dir)
        
        embeddings = [
            [0.1 * i for i in range(50)]
            for _ in range(3)
        ]
        
        docs = [
            Document(
                content=f"Document {i}",
                metadata={"index": i},
                source="test",
                doc_id=f"doc_{i}"
            )
            for i in range(3)
        ]
        
        for doc, emb in zip(docs, embeddings):
            await store.save(doc, emb)
        
        # Verify all saved
        doc_ids = await store.list_all()
        assert len(doc_ids) == 3
    
    @pytest.mark.asyncio
    async def test_persistence_document_integrity(self, temp_dir):
        """Test that document integrity is preserved through persistence."""
        store = FileSystemStore(base_dir=temp_dir)
        
        original = Document(
            content="Important content here",
            metadata={"type": "test", "priority": 1},
            source="important_source"
        )
        
        embedding = [0.5] * 100
        
        await store.save(original, embedding)
        result = await store.load(original.doc_id)
        
        assert result is not None
        loaded, loaded_emb = result
        
        # Check all fields preserved
        assert loaded.content == original.content
        assert loaded.metadata == original.metadata
        assert loaded.source == original.source
        assert loaded.doc_id == original.doc_id
        assert loaded_emb == embedding
    
    @pytest.mark.asyncio
    async def test_persistence_overwrite(self, temp_dir, sample_embedding):
        """Test overwriting existing document."""
        store = FileSystemStore(base_dir=temp_dir)
        
        doc_id = "test_doc"
        
        # Create first document
        doc1 = Document(
            content="Original content",
            source="test",
            doc_id=doc_id
        )
        
        await store.save(doc1, sample_embedding)
        
        # Create updated document with same ID
        doc2 = Document(
            content="Updated content",
            source="test",
            doc_id=doc_id
        )
        
        await store.save(doc2, sample_embedding)
        
        # Load should return updated version
        result = await store.load(doc_id)
        
        assert result is not None
        loaded, _ = result
        assert loaded.content == "Updated content"


class TestStoreOperations:
    """Tests for common store operations."""
    
    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, temp_dir):
        """Test deleting nonexistent document."""
        store = FileSystemStore(base_dir=temp_dir)
        
        deleted = await store.delete("nonexistent")
        
        assert not deleted
    
    @pytest.mark.asyncio
    async def test_list_empty_store(self, temp_dir):
        """Test listing empty store."""
        store = FileSystemStore(base_dir=temp_dir)
        
        doc_ids = await store.list_all()
        
        assert doc_ids == []
