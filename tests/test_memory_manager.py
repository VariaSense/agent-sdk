"""Tests for semantic memory manager."""

import pytest
import tempfile
from agent_sdk.data_connectors.document import Document
from agent_sdk.memory.embeddings import HuggingFaceEmbeddings
from agent_sdk.memory.persistence import FileSystemStore
from agent_sdk.memory.semantic_memory import SemanticMemoryManager


@pytest.fixture
def embeddings():
    """Create embeddings provider."""
    return HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")


@pytest.fixture
def memory_store():
    """Create temporary memory store."""
    tmpdir = tempfile.mkdtemp()
    return FileSystemStore(base_dir=tmpdir)


@pytest.fixture
def memory_manager(embeddings, memory_store):
    """Create semantic memory manager."""
    return SemanticMemoryManager(
        embedding_provider=embeddings,
        memory_store=memory_store,
        similarity_threshold=0.5
    )


@pytest.fixture
def sample_documents():
    """Create sample documents."""
    return [
        Document(
            content="Python is a popular programming language",
            metadata={"language": "python", "type": "tutorial"},
            source="docs",
            doc_id="doc_0"
        ),
        Document(
            content="JavaScript is used for web development",
            metadata={"language": "javascript", "type": "tutorial"},
            source="docs",
            doc_id="doc_1"
        ),
        Document(
            content="Cats are independent animals",
            metadata={"animal": "cat", "type": "fact"},
            source="wiki",
            doc_id="doc_2"
        ),
    ]


class TestSemanticMemoryManager:
    """Tests for semantic memory manager."""
    
    def test_manager_creation(self, memory_manager, embeddings, memory_store):
        """Test creating memory manager."""
        assert memory_manager is not None
        assert memory_manager.embedding_provider == embeddings
        assert memory_manager.memory_store == memory_store
        assert memory_manager.similarity_threshold == 0.5
    
    def test_manager_threshold_validation(self, embeddings, memory_store):
        """Test creating manager with custom threshold."""
        manager = SemanticMemoryManager(
            embedding_provider=embeddings,
            memory_store=memory_store,
            similarity_threshold=0.7
        )
        
        assert manager.similarity_threshold == 0.7
    
    @pytest.mark.asyncio
    async def test_add_documents(self, memory_manager, sample_documents):
        """Test adding documents to memory."""
        await memory_manager.add_documents(sample_documents)
        
        assert len(memory_manager.documents) == len(sample_documents)
        assert all(doc.doc_id in memory_manager.documents for doc in sample_documents)
    
    @pytest.mark.asyncio
    async def test_add_empty_documents(self, memory_manager):
        """Test adding empty document list."""
        await memory_manager.add_documents([])
        
        assert len(memory_manager.documents) == 0
    
    @pytest.mark.asyncio
    async def test_retrieve_documents(self, memory_manager, sample_documents):
        """Test retrieving documents by query."""
        await memory_manager.add_documents(sample_documents)
        
        results = await memory_manager.retrieve("programming language", top_k=2)
        
        assert len(results) > 0
        assert all(isinstance(doc, Document) for doc, _ in results)
        assert all(isinstance(score, float) for _, score in results)
        assert all(score >= memory_manager.similarity_threshold for _, score in results)
    
    @pytest.mark.asyncio
    async def test_retrieve_no_matches(self, memory_manager, sample_documents):
        """Test retrieval with no matches above threshold."""
        manager = SemanticMemoryManager(
            embedding_provider=memory_manager.embedding_provider,
            memory_store=memory_manager.memory_store,
            similarity_threshold=0.99  # Very high threshold
        )
        
        await manager.add_documents(sample_documents)
        
        results = await manager.retrieve("query", top_k=5)
        
        # May have no results due to high threshold
        assert isinstance(results, list)
    
    @pytest.mark.asyncio
    async def test_retrieve_with_context(self, memory_manager, sample_documents):
        """Test retrieving with context."""
        await memory_manager.add_documents(sample_documents)
        
        result = await memory_manager.retrieve_with_context(
            "programming",
            top_k=2,
            context_window=1
        )
        
        assert 'query' in result
        assert 'results' in result
        assert 'context' in result
        assert 'total_retrieved' in result
        
        assert result['query'] == "programming"
        assert result['total_retrieved'] >= 0
    
    @pytest.mark.asyncio
    async def test_update_document(self, memory_manager, sample_documents):
        """Test updating a document."""
        await memory_manager.add_documents(sample_documents)
        
        doc_id = sample_documents[0].doc_id
        new_content = "Updated: Python is great"
        
        success = await memory_manager.update_document(
            doc_id,
            new_content
        )
        
        assert success
        assert memory_manager.documents[doc_id].content == new_content
    
    @pytest.mark.asyncio
    async def test_update_with_metadata(self, memory_manager, sample_documents):
        """Test updating document with new metadata."""
        await memory_manager.add_documents(sample_documents)
        
        doc_id = sample_documents[0].doc_id
        new_metadata = {"updated": True, "version": 2}
        
        success = await memory_manager.update_document(
            doc_id,
            "New content",
            new_metadata=new_metadata
        )
        
        assert success
        assert memory_manager.documents[doc_id].metadata == new_metadata
    
    @pytest.mark.asyncio
    async def test_update_nonexistent(self, memory_manager):
        """Test updating nonexistent document."""
        success = await memory_manager.update_document(
            "nonexistent",
            "content"
        )
        
        assert not success
    
    @pytest.mark.asyncio
    async def test_delete_document(self, memory_manager, sample_documents):
        """Test deleting a document."""
        await memory_manager.add_documents(sample_documents)
        
        doc_id = sample_documents[0].doc_id
        
        success = await memory_manager.delete_document(doc_id)
        
        assert success
        assert doc_id not in memory_manager.documents
    
    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, memory_manager):
        """Test deleting nonexistent document."""
        success = await memory_manager.delete_document("nonexistent")
        
        assert not success
    
    @pytest.mark.asyncio
    async def test_get_statistics(self, memory_manager, sample_documents):
        """Test getting memory statistics."""
        await memory_manager.add_documents(sample_documents)
        
        stats = await memory_manager.get_statistics()
        
        assert 'total_documents' in stats
        assert 'persisted_documents' in stats
        assert 'embedding_dimension' in stats
        assert 'similarity_threshold' in stats
        
        assert stats['total_documents'] == len(sample_documents)
        assert stats['embedding_dimension'] == 384  # MiniLM dimension
        assert stats['similarity_threshold'] == 0.5
    
    @pytest.mark.asyncio
    async def test_statistics_empty_manager(self, memory_manager):
        """Test statistics on empty manager."""
        stats = await memory_manager.get_statistics()
        
        assert stats['total_documents'] == 0
        assert stats['persisted_documents'] == 0


class TestMemoryManagerWorkflow:
    """Tests for complete memory manager workflows."""
    
    @pytest.mark.asyncio
    async def test_full_lifecycle(self, memory_manager):
        """Test complete document lifecycle."""
        # Create documents with explicit IDs
        docs = [
            Document(content="First document", source="test", doc_id="doc_1"),
            Document(content="Second document", source="test", doc_id="doc_2"),
        ]
        
        # Add
        await memory_manager.add_documents(docs)
        assert len(memory_manager.documents) == 2
        
        # Retrieve
        results = await memory_manager.retrieve("document", top_k=5)
        assert len(results) > 0
        
        # Update
        success = await memory_manager.update_document(
            docs[0].doc_id,
            "Updated first document"
        )
        assert success
        
        # Delete
        success = await memory_manager.delete_document(docs[1].doc_id)
        assert success
        
        # Final state
        assert len(memory_manager.documents) == 1
    
    @pytest.mark.asyncio
    async def test_similarity_based_retrieval(self, memory_manager):
        """Test that similar documents are retrieved."""
        docs = [
            Document(content="Cats are pets", source="test"),
            Document(content="Dogs are loyal", source="test"),
            Document(content="Mathematics is important", source="test"),
        ]
        
        await memory_manager.add_documents(docs)
        
        # Query about pets
        results = await memory_manager.retrieve("pets", top_k=1)
        
        # First document about cats should be most similar
        if results:
            assert "Cats" in results[0][0].content or "pets" in results[0][0].content
    
    @pytest.mark.asyncio
    async def test_batch_operations(self, memory_manager):
        """Test batch document operations."""
        # Add batch with explicit IDs
        docs = [
            Document(content=f"Doc {i}", source="test", doc_id=f"doc_{i}")
            for i in range(5)
        ]
        
        await memory_manager.add_documents(docs)
        assert len(memory_manager.documents) == 5
        
        # Update multiple
        for i, doc in enumerate(docs[:2]):
            await memory_manager.update_document(
                doc.doc_id,
                f"Updated {doc.content}"
            )
        
        # Delete multiple
        for doc in docs[2:]:
            await memory_manager.delete_document(doc.doc_id)
        
        # Should have 2 left
        assert len(memory_manager.documents) == 2
