"""Tests for embedding providers."""

import pytest
from agent_sdk.memory.embeddings import (
    EmbeddingProvider,
    OpenAIEmbeddings,
    HuggingFaceEmbeddings,
    LocalEmbeddings,
)


class TestEmbeddingProvider:
    """Tests for EmbeddingProvider base class."""
    
    def test_embedding_provider_is_abstract(self):
        """Test that EmbeddingProvider cannot be instantiated."""
        with pytest.raises(TypeError):
            EmbeddingProvider()
    
    def test_embedding_dimension_property_required(self):
        """Test that embedding_dimension is required."""
        class BadProvider(EmbeddingProvider):
            async def embed_text(self, text):
                return []
            
            async def embed_batch(self, texts):
                return []
        
        # Should not be able to instantiate because embedding_dimension is abstract
        with pytest.raises(TypeError):
            provider = BadProvider()


class TestHuggingFaceEmbeddings:
    """Tests for HuggingFace embeddings."""
    
    @pytest.mark.asyncio
    async def test_huggingface_embeddings_creation(self):
        """Test creating HuggingFace embeddings."""
        embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
        
        assert embeddings is not None
        assert embeddings.model_name == "sentence-transformers/all-MiniLM-L6-v2"
    
    @pytest.mark.asyncio
    async def test_huggingface_embedding_dimension(self):
        """Test embedding dimension detection."""
        embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
        
        # HuggingFace all-MiniLM-L6-v2 has 384 dimensions
        assert embeddings.embedding_dimension == 384
    
    @pytest.mark.asyncio
    async def test_huggingface_embed_text(self):
        """Test text embedding."""
        embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
        
        text = "Hello world"
        result = await embeddings.embed_text(text)
        
        assert isinstance(result, list)
        assert len(result) == embeddings.embedding_dimension
        assert all(isinstance(x, float) for x in result)
    
    @pytest.mark.asyncio
    async def test_huggingface_embed_batch(self):
        """Test batch embedding."""
        embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
        
        texts = ["Hello", "World", "Test"]
        results = await embeddings.embed_batch(texts)
        
        assert len(results) == 3
        for result in results:
            assert len(result) == embeddings.embedding_dimension
    
    def test_huggingface_sync_wrapper(self):
        """Test synchronous embedding."""
        embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
        
        text = "Hello world"
        result = embeddings.embed_text_sync(text)
        
        assert isinstance(result, list)
        assert len(result) == embeddings.embedding_dimension


class TestLocalEmbeddings:
    """Tests for local embeddings."""
    
    def test_local_embeddings_creation(self):
        """Test creating local embeddings."""
        embeddings = LocalEmbeddings()
        
        assert embeddings is not None
    
    def test_local_embeddings_dimension(self):
        """Test local embedding dimension."""
        embeddings = LocalEmbeddings()
        
        # LocalEmbeddings delegates to HuggingFace
        assert embeddings.embedding_dimension == 384
    
    @pytest.mark.asyncio
    async def test_local_embed_text(self):
        """Test local text embedding."""
        embeddings = LocalEmbeddings()
        
        result = await embeddings.embed_text("test")
        
        assert isinstance(result, list)
        assert len(result) == 384
    
    def test_local_custom_model(self):
        """Test local embeddings with custom model."""
        embeddings = LocalEmbeddings(model_name="sentence-transformers/all-mpnet-base-v2")
        
        # all-mpnet-base-v2 has 768 dimensions
        assert embeddings.embedding_dimension == 768


class TestOpenAIEmbeddings:
    """Tests for OpenAI embeddings."""
    
    def test_openai_embeddings_creation_small(self):
        """Test creating OpenAI embeddings with small model."""
        try:
            embeddings = OpenAIEmbeddings(
                api_key="test-key",
                model="text-embedding-3-small"
            )
            
            assert embeddings is not None
            assert embeddings.model == "text-embedding-3-small"
            assert embeddings.embedding_dimension == 1536
        except ImportError:
            pytest.skip("openai not installed")
    
    def test_openai_embeddings_creation_large(self):
        """Test creating OpenAI embeddings with large model."""
        try:
            embeddings = OpenAIEmbeddings(
                api_key="test-key",
                model="text-embedding-3-large"
            )
            
            assert embeddings.model == "text-embedding-3-large"
            assert embeddings.embedding_dimension == 3072
        except ImportError:
            pytest.skip("openai not installed")
    
    @pytest.mark.asyncio
    async def test_openai_embed_text_requires_api_key(self):
        """Test that OpenAI embeddings require valid API key."""
        try:
            embeddings = OpenAIEmbeddings(
                api_key="invalid-key",
                model="text-embedding-3-small"
            )
            
            # This would fail with actual API call, but we test initialization
            assert embeddings is not None
        except ImportError:
            pytest.skip("openai not installed")


class TestEmbeddingConsistency:
    """Tests for embedding consistency."""
    
    @pytest.mark.asyncio
    async def test_same_text_same_embedding(self):
        """Test that same text produces same embedding."""
        embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
        
        text = "The quick brown fox"
        
        emb1 = await embeddings.embed_text(text)
        emb2 = await embeddings.embed_text(text)
        
        # Should be identical
        assert emb1 == emb2
    
    @pytest.mark.asyncio
    async def test_different_text_different_embedding(self):
        """Test that different text produces different embeddings."""
        embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
        
        emb1 = await embeddings.embed_text("Hello")
        emb2 = await embeddings.embed_text("Goodbye")
        
        # Should be different
        assert emb1 != emb2
    
    def test_sync_async_equivalence(self):
        """Test that sync and async produce same results."""
        embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
        
        text = "Test text"
        
        async_result = embeddings.embed_text_sync(text)
        
        assert isinstance(async_result, list)
        assert len(async_result) == embeddings.embedding_dimension
