"""Tests for semantic search engine."""

import pytest
from agent_sdk.data_connectors.document import Document
from agent_sdk.memory.embeddings import HuggingFaceEmbeddings
from agent_sdk.memory.semantic_search import (
    SemanticSearchEngine,
    SimilaritySearch,
    HybridSearch,
    MMRSearch,
)


@pytest.fixture
def embeddings():
    """Create embeddings provider."""
    return HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")


@pytest.fixture
def sample_documents():
    """Create sample documents."""
    return [
        Document(
            content="Python is a programming language",
            metadata={"type": "tutorial"},
            source="test",
            doc_id="doc_0"
        ),
        Document(
            content="JavaScript runs in web browsers",
            metadata={"type": "tutorial"},
            source="test",
            doc_id="doc_1"
        ),
        Document(
            content="Cats are feline animals",
            metadata={"type": "fact"},
            source="test",
            doc_id="doc_2"
        ),
        Document(
            content="Dogs are loyal pets",
            metadata={"type": "fact"},
            source="test",
            doc_id="doc_3"
        ),
    ]


class TestSimilaritySearch:
    """Tests for similarity search strategy."""
    
    def test_similarity_search_creation(self):
        """Test creating similarity search."""
        search = SimilaritySearch()
        assert search is not None
    
    @pytest.mark.asyncio
    async def test_similarity_search_basic(self, embeddings, sample_documents):
        """Test basic similarity search."""
        engine = SemanticSearchEngine(embeddings, strategy=SimilaritySearch())
        
        # Index documents
        await engine.index(sample_documents)
        
        # Search
        results = await engine.search("programming language", top_k=2)
        
        assert len(results) <= 2
        assert all(isinstance(doc, Document) for doc, _ in results)
        assert all(isinstance(score, float) for _, score in results)
    
    @pytest.mark.asyncio
    async def test_similarity_search_exact_match(self, embeddings):
        """Test similarity search with exact match."""
        doc = Document(
            content="The quick brown fox jumps over the lazy dog",
            source="test"
        )
        
        engine = SemanticSearchEngine(embeddings)
        await engine.index([doc])
        
        results = await engine.search("quick brown fox", top_k=1)
        
        assert len(results) == 1
        assert results[0][0].content == doc.content
        assert results[0][1] > 0.7  # High similarity
    
    def test_cosine_similarity(self):
        """Test cosine similarity calculation."""
        v1 = [1.0, 0.0, 0.0]
        v2 = [1.0, 0.0, 0.0]
        v3 = [0.0, 1.0, 0.0]
        
        search = SimilaritySearch()
        
        # Identical vectors should have similarity 1.0
        sim12 = search._cosine_similarity(v1, v2)
        assert sim12 == 1.0
        
        # Orthogonal vectors should have similarity 0.0
        sim13 = search._cosine_similarity(v1, v3)
        assert sim13 == 0.0
    
    def test_cosine_similarity_different_lengths(self):
        """Test cosine similarity with different vector lengths."""
        v1 = [1.0, 0.0]
        v2 = [1.0, 0.0, 0.0]
        
        search = SimilaritySearch()
        sim = search._cosine_similarity(v1, v2)
        
        assert sim == 0.0  # Different lengths return 0


class TestHybridSearch:
    """Tests for hybrid search strategy."""
    
    def test_hybrid_search_creation(self):
        """Test creating hybrid search."""
        search = HybridSearch(semantic_weight=0.8)
        assert search is not None
        assert search.semantic_weight == 0.8
        assert abs(search.metadata_weight - 0.2) < 1e-9
    
    def test_hybrid_search_invalid_weight(self):
        """Test hybrid search with invalid weight."""
        with pytest.raises(ValueError):
            HybridSearch(semantic_weight=1.5)
        
        with pytest.raises(ValueError):
            HybridSearch(semantic_weight=-0.1)
    
    @pytest.mark.asyncio
    async def test_hybrid_search_with_filter(self, embeddings, sample_documents):
        """Test hybrid search with metadata filter."""
        engine = SemanticSearchEngine(embeddings, strategy=HybridSearch())
        
        await engine.index(sample_documents)
        
        # Search with filter
        results = await engine.search(
            "animals",
            top_k=5,
            metadata_filter={"type": "fact"}
        )
        
        # Should only return documents with type=fact
        assert all(doc.get_metadata("type") == "fact" for doc, _ in results)
    
    def test_metadata_filter_matching(self):
        """Test metadata filter matching."""
        doc = Document(
            content="test",
            metadata={"type": "fact", "color": "blue"},
            source="test"
        )
        
        search = HybridSearch()
        
        # Should match
        assert search._matches_filter(doc, {"type": "fact"})
        assert search._matches_filter(doc, {"color": "blue"})
        assert search._matches_filter(doc, {"type": "fact", "color": "blue"})
        
        # Should not match
        assert not search._matches_filter(doc, {"type": "tutorial"})
        assert not search._matches_filter(doc, {"color": "red"})


class TestMMRSearch:
    """Tests for Maximal Marginal Relevance search."""
    
    def test_mmr_search_creation(self):
        """Test creating MMR search."""
        search = MMRSearch(diversity_penalty=0.5)
        assert search is not None
        assert search.diversity_penalty == 0.5
    
    def test_mmr_search_invalid_penalty(self):
        """Test MMR search with invalid diversity penalty."""
        with pytest.raises(ValueError):
            MMRSearch(diversity_penalty=1.5)
        
        with pytest.raises(ValueError):
            MMRSearch(diversity_penalty=-0.1)
    
    @pytest.mark.asyncio
    async def test_mmr_search_diversity(self, embeddings):
        """Test MMR search promotes diversity."""
        docs = [
            Document(content="Python programming language", source="test"),
            Document(content="Python software development", source="test"),
            Document(content="Java programming language", source="test"),
            Document(content="Cats are animals", source="test"),
        ]
        
        engine = SemanticSearchEngine(embeddings, strategy=MMRSearch(diversity_penalty=0.8))
        
        await engine.index(docs)
        
        results = await engine.search("programming", top_k=2)
        
        # Should prefer diverse results even if similar
        assert len(results) <= 2


class TestSemanticSearchEngine:
    """Tests for semantic search engine."""
    
    @pytest.mark.asyncio
    async def test_search_engine_creation(self, embeddings):
        """Test creating search engine."""
        engine = SemanticSearchEngine(embeddings)
        
        assert engine is not None
        assert engine.embedding_provider == embeddings
        assert isinstance(engine.strategy, SimilaritySearch)
    
    @pytest.mark.asyncio
    async def test_search_engine_index_empty(self, embeddings):
        """Test indexing empty document list."""
        engine = SemanticSearchEngine(embeddings)
        
        await engine.index([])
        
        assert len(engine.documents) == 0
    
    @pytest.mark.asyncio
    async def test_search_engine_search_empty(self, embeddings):
        """Test searching empty index."""
        engine = SemanticSearchEngine(embeddings)
        
        results = await engine.search("query", top_k=5)
        
        assert results == []
    
    @pytest.mark.asyncio
    async def test_search_engine_full_workflow(self, embeddings, sample_documents):
        """Test complete search workflow."""
        engine = SemanticSearchEngine(embeddings)
        
        # Index
        await engine.index(sample_documents)
        
        assert len(engine.documents) == len(sample_documents)
        assert len(engine.embeddings) == len(sample_documents)
        
        # Search
        results = await engine.search("animal", top_k=2)
        
        assert 0 < len(results) <= 2
    
    def test_search_engine_sync(self, embeddings, sample_documents):
        """Test synchronous search wrapper."""
        engine = SemanticSearchEngine(embeddings)
        
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(engine.index(sample_documents))
        finally:
            loop.close()
        
        results = engine.search_sync("programming", top_k=2)
        
        assert len(results) > 0


class TestSearchStrategies:
    """Tests comparing different search strategies."""
    
    @pytest.mark.asyncio
    async def test_different_strategies_same_documents(self, embeddings, sample_documents):
        """Test that different strategies work on same documents."""
        strategies = [
            SimilaritySearch(),
            HybridSearch(semantic_weight=0.7),
            MMRSearch(diversity_penalty=0.6),
        ]
        
        for strategy in strategies:
            engine = SemanticSearchEngine(embeddings, strategy=strategy)
            await engine.index(sample_documents)
            
            results = await engine.search("programming", top_k=2)
            
            assert len(results) > 0
            assert all(isinstance(doc, Document) for doc, _ in results)
