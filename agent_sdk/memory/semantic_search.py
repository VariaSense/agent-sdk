"""Semantic search engine for similarity-based document retrieval."""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
from agent_sdk.data_connectors.document import Document, Chunk
from agent_sdk.memory.embeddings import EmbeddingProvider
import math


class RetrievalStrategy(ABC):
    """Base class for retrieval strategies."""
    
    @abstractmethod
    def retrieve(
        self,
        query_embedding: List[float],
        documents: List[Tuple[Document, List[float]]],
        top_k: int = 5
    ) -> List[Tuple[Document, float]]:
        """Retrieve relevant documents.
        
        Args:
            query_embedding: Query embedding vector.
            documents: List of (document, embedding) tuples.
            top_k: Number of results to return.
            
        Returns:
            List of (document, similarity_score) tuples.
        """
        pass


class SimilaritySearch(RetrievalStrategy):
    """Simple similarity-based retrieval using cosine distance."""
    
    def retrieve(
        self,
        query_embedding: List[float],
        documents: List[Tuple[Document, List[float]]],
        top_k: int = 5
    ) -> List[Tuple[Document, float]]:
        """Retrieve by cosine similarity.
        
        Args:
            query_embedding: Query embedding vector.
            documents: List of (document, embedding) tuples.
            top_k: Number of results to return.
            
        Returns:
            Top-k most similar documents with scores.
        """
        scores = []
        
        for doc, embedding in documents:
            similarity = self._cosine_similarity(query_embedding, embedding)
            scores.append((doc, similarity))
        
        # Sort by similarity descending
        scores.sort(key=lambda x: x[1], reverse=True)
        
        return scores[:top_k]
    
    @staticmethod
    def _cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between vectors.
        
        Args:
            vec1: First vector.
            vec2: Second vector.
            
        Returns:
            Similarity score (0-1).
        """
        if len(vec1) != len(vec2):
            return 0.0
        
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)


class HybridSearch(RetrievalStrategy):
    """Hybrid search combining semantic similarity and metadata filtering."""
    
    def __init__(self, semantic_weight: float = 0.8):
        """Initialize hybrid search.
        
        Args:
            semantic_weight: Weight for semantic similarity (0-1).
        """
        if not 0 <= semantic_weight <= 1:
            raise ValueError("semantic_weight must be between 0 and 1")
        
        self.semantic_weight = semantic_weight
        self.metadata_weight = 1 - semantic_weight
        self._similarity = SimilaritySearch()
    
    def retrieve(
        self,
        query_embedding: List[float],
        documents: List[Tuple[Document, List[float]]],
        top_k: int = 5,
        metadata_filter: Optional[Dict[str, Any]] = None
    ) -> List[Tuple[Document, float]]:
        """Retrieve using hybrid scoring.
        
        Args:
            query_embedding: Query embedding vector.
            documents: List of (document, embedding) tuples.
            top_k: Number of results to return.
            metadata_filter: Optional metadata filtering criteria.
            
        Returns:
            Top-k documents with hybrid scores.
        """
        # Get semantic scores
        semantic_results = self._similarity.retrieve(
            query_embedding,
            documents,
            top_k=len(documents)  # Get all for scoring
        )
        
        # Apply metadata filter if provided
        if metadata_filter:
            semantic_results = [
                (doc, score) for doc, score in semantic_results
                if self._matches_filter(doc, metadata_filter)
            ]
        
        return semantic_results[:top_k]
    
    @staticmethod
    def _matches_filter(doc: Document, filter_dict: Dict[str, Any]) -> bool:
        """Check if document matches metadata filter.
        
        Args:
            doc: Document to check.
            filter_dict: Filter criteria.
            
        Returns:
            True if document matches filter.
        """
        for key, value in filter_dict.items():
            if doc.get_metadata(key) != value:
                return False
        return True


class MMRSearch(RetrievalStrategy):
    """Maximize Marginal Relevance search to reduce redundancy."""
    
    def __init__(self, diversity_penalty: float = 0.5):
        """Initialize MMR search.
        
        Args:
            diversity_penalty: Penalty for similar results (0-1).
        """
        if not 0 <= diversity_penalty <= 1:
            raise ValueError("diversity_penalty must be between 0 and 1")
        
        self.diversity_penalty = diversity_penalty
        self._similarity = SimilaritySearch()
    
    def retrieve(
        self,
        query_embedding: List[float],
        documents: List[Tuple[Document, List[float]]],
        top_k: int = 5
    ) -> List[Tuple[Document, float]]:
        """Retrieve using Maximal Marginal Relevance.
        
        Args:
            query_embedding: Query embedding vector.
            documents: List of (document, embedding) tuples.
            top_k: Number of results to return.
            
        Returns:
            Top-k diverse documents with MMR scores.
        """
        if not documents:
            return []
        
        # Calculate initial relevance scores
        relevance_scores = {
            i: self._similarity._cosine_similarity(query_embedding, emb)
            for i, (_, emb) in enumerate(documents)
        }
        
        # Start with most relevant
        selected = []
        remaining = set(range(len(documents)))
        
        # Select first document
        first_idx = max(remaining, key=lambda i: relevance_scores[i])
        selected.append(first_idx)
        remaining.remove(first_idx)
        
        # Greedily select remaining documents
        while len(selected) < top_k and remaining:
            best_idx = None
            best_mmr = -1
            
            for idx in remaining:
                relevance = relevance_scores[idx]
                
                # Calculate maximum redundancy with selected items
                max_redundancy = 0
                for selected_idx in selected:
                    _, sel_emb = documents[selected_idx]
                    _, cand_emb = documents[idx]
                    redundancy = self._similarity._cosine_similarity(sel_emb, cand_emb)
                    max_redundancy = max(max_redundancy, redundancy)
                
                # MMR score = relevance - diversity_penalty * redundancy
                mmr_score = relevance - self.diversity_penalty * max_redundancy
                
                if mmr_score > best_mmr:
                    best_mmr = mmr_score
                    best_idx = idx
            
            if best_idx is not None:
                selected.append(best_idx)
                remaining.remove(best_idx)
        
        # Return selected documents with scores
        return [
            (documents[idx][0], relevance_scores[idx])
            for idx in selected
        ]


class SemanticSearchEngine:
    """Semantic search engine for document retrieval."""
    
    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        strategy: Optional[RetrievalStrategy] = None
    ):
        """Initialize search engine.
        
        Args:
            embedding_provider: Provider for generating embeddings.
            strategy: Retrieval strategy (default: SimilaritySearch).
        """
        self.embedding_provider = embedding_provider
        self.strategy = strategy or SimilaritySearch()
        
        self.documents: List[Document] = []
        self.embeddings: Dict[str, List[float]] = {}
    
    async def index(self, documents: List[Document]) -> None:
        """Index documents for semantic search.
        
        Args:
            documents: Documents to index.
        """
        self.documents = documents
        
        # Generate embeddings
        texts = [doc.content for doc in documents]
        embeddings = await self.embedding_provider.embed_batch(texts)
        
        # Store embeddings
        for doc, embedding in zip(documents, embeddings):
            self.embeddings[doc.doc_id] = embedding
    
    async def search(
        self,
        query: str,
        top_k: int = 5,
        metadata_filter: Optional[Dict[str, Any]] = None
    ) -> List[Tuple[Document, float]]:
        """Search for documents similar to query.
        
        Args:
            query: Search query.
            top_k: Number of results to return.
            metadata_filter: Optional metadata filter.
            
        Returns:
            List of (document, similarity_score) tuples.
        """
        if not self.documents:
            return []
        
        # Generate query embedding
        query_embedding = await self.embedding_provider.embed_text(query)
        
        # Get document embeddings
        doc_embeddings = [
            (doc, self.embeddings[doc.doc_id])
            for doc in self.documents
            if doc.doc_id in self.embeddings
        ]
        
        # Retrieve using strategy
        if isinstance(self.strategy, HybridSearch):
            results = self.strategy.retrieve(
                query_embedding,
                doc_embeddings,
                top_k=top_k,
                metadata_filter=metadata_filter
            )
        else:
            results = self.strategy.retrieve(
                query_embedding,
                doc_embeddings,
                top_k=top_k
            )
        
        return results
    
    def search_sync(
        self,
        query: str,
        top_k: int = 5,
        metadata_filter: Optional[Dict[str, Any]] = None
    ) -> List[Tuple[Document, float]]:
        """Synchronous search wrapper.
        
        Args:
            query: Search query.
            top_k: Number of results.
            metadata_filter: Optional metadata filter.
            
        Returns:
            List of (document, similarity_score) tuples.
        """
        import asyncio
        
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(
                self.search(query, top_k, metadata_filter)
            )
        finally:
            loop.close()
