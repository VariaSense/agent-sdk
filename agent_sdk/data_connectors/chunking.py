"""Document chunking strategies for embeddings and processing."""

from abc import ABC, abstractmethod
from typing import List, Optional
from agent_sdk.data_connectors.document import Document, Chunk


class ChunkingStrategy(ABC):
    """Base class for document chunking strategies."""
    
    @abstractmethod
    def chunk(self, document: Document) -> List[Chunk]:
        """Split document into chunks.
        
        Args:
            document: Document to chunk.
            
        Returns:
            List of Chunk objects.
        """
        pass


class CharacterChunker(ChunkingStrategy):
    """Split documents by character count."""
    
    def __init__(self, chunk_size: int = 1000, overlap: int = 200):
        """Initialize character chunker.
        
        Args:
            chunk_size: Number of characters per chunk.
            overlap: Number of overlapping characters between chunks.
        """
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if overlap >= chunk_size:
            raise ValueError("overlap must be less than chunk_size")
        
        self.chunk_size = chunk_size
        self.overlap = overlap
    
    def chunk(self, document: Document) -> List[Chunk]:
        """Split document by character count.
        
        Args:
            document: Document to chunk.
            
        Returns:
            List of Chunk objects.
        """
        content = document.content
        chunks = []
        
        if len(content) == 0:
            return chunks
        
        start = 0
        chunk_number = 0
        
        while start < len(content):
            # Calculate end position
            end = min(start + self.chunk_size, len(content))
            
            # Extract chunk
            chunk_text = content[start:end]
            
            # Create chunk object
            chunk = Chunk(
                content=chunk_text,
                document_id=document.doc_id,
                chunk_number=chunk_number,
                metadata={
                    **document.metadata,
                    "chunking_strategy": "character",
                    "chunk_start": start,
                    "chunk_end": end,
                },
            )
            chunks.append(chunk)
            if end >= len(content):
                break

            # Move to next chunk
            start = end - self.overlap
            chunk_number += 1
        
        return chunks


class TokenChunker(ChunkingStrategy):
    """Split documents by token count (for embeddings)."""
    
    def __init__(self, max_tokens: int = 512, overlap: int = 50, model: str = "gpt2"):
        """Initialize token chunker.
        
        Args:
            max_tokens: Maximum tokens per chunk.
            overlap: Number of overlapping tokens.
            model: Tokenizer model to use.
        """
        if max_tokens <= 0:
            raise ValueError("max_tokens must be positive")
        if overlap >= max_tokens:
            raise ValueError("overlap must be less than max_tokens")
        
        self.max_tokens = max_tokens
        self.overlap = overlap
        self.model = model
        self._tokenizer = self._load_tokenizer()
    
    def _load_tokenizer(self):
        """Load appropriate tokenizer.
        
        Returns:
            Tokenizer or None if not available.
        """
        try:
            import tiktoken
            try:
                return tiktoken.get_encoding(self.model)
            except Exception:
                # Fallback to simple whitespace tokenizer
                return None
        except ImportError:
            return None
    
    def chunk(self, document: Document) -> List[Chunk]:
        """Split document by token count.
        
        Args:
            document: Document to chunk.
            
        Returns:
            List of Chunk objects.
        """
        content = document.content
        
        if not content:
            return []
        
        # Use tokenizer if available, otherwise approximate
        if self._tokenizer:
            return self._chunk_with_tokenizer(document)
        else:
            return self._chunk_with_approximation(document)
    
    def _chunk_with_tokenizer(self, document: Document) -> List[Chunk]:
        """Chunk using actual tokenizer.
        
        Args:
            document: Document to chunk.
            
        Returns:
            List of chunks.
        """
        try:
            tokens = self._tokenizer.encode(document.content)
            
            chunks = []
            chunk_number = 0
            start_idx = 0
            
            while start_idx < len(tokens):
                end_idx = min(start_idx + self.max_tokens, len(tokens))
                
                # Decode tokens back to text
                chunk_tokens = tokens[start_idx:end_idx]
                chunk_text = self._tokenizer.decode(chunk_tokens)
                
                chunk = Chunk(
                    content=chunk_text,
                    document_id=document.doc_id,
                    chunk_number=chunk_number,
                    metadata={
                        **document.metadata,
                        "chunking_strategy": "token",
                        "token_count": len(chunk_tokens),
                    },
                )
                chunks.append(chunk)
                if end_idx >= len(tokens):
                    break

                start_idx = end_idx - self.overlap
                chunk_number += 1
            
            return chunks
        except Exception:
            # Fallback to approximation
            return self._chunk_with_approximation(document)
    
    def _chunk_with_approximation(self, document: Document) -> List[Chunk]:
        """Chunk using approximate token estimation.
        
        Args:
            document: Document to chunk.
            
        Returns:
            List of chunks.
        """
        # Approximate: ~4 characters per token
        char_per_token = 4
        chunk_size = self.max_tokens * char_per_token
        overlap_size = self.overlap * char_per_token
        
        content = document.content
        chunks = []
        chunk_number = 0
        start = 0
        
        while start < len(content):
            end = min(start + chunk_size, len(content))
            chunk_text = content[start:end]
            
            # Estimate token count
            token_count = len(chunk_text) // char_per_token
            
            chunk = Chunk(
                content=chunk_text,
                document_id=document.doc_id,
                chunk_number=chunk_number,
                metadata={
                    **document.metadata,
                    "chunking_strategy": "token_approximate",
                    "estimated_token_count": token_count,
                },
            )
            chunks.append(chunk)
            if end >= len(content):
                break

            start = end - overlap_size
            chunk_number += 1
        
        return chunks


class SemanticChunker(ChunkingStrategy):
    """Split documents by semantic similarity boundaries."""
    
    def __init__(self, similarity_threshold: float = 0.5):
        """Initialize semantic chunker.
        
        Args:
            similarity_threshold: Minimum similarity to keep together (0-1).
        """
        if not 0 <= similarity_threshold <= 1:
            raise ValueError("similarity_threshold must be between 0 and 1")
        
        self.similarity_threshold = similarity_threshold
        self._sentence_transformer = self._load_sentence_transformer()
    
    @staticmethod
    def _load_sentence_transformer():
        """Load sentence transformer model.
        
        Returns:
            Model or None if not available.
        """
        try:
            from sentence_transformers import SentenceTransformer
            return SentenceTransformer('all-MiniLM-L6-v2')
        except ImportError:
            return None
    
    def chunk(self, document: Document) -> List[Chunk]:
        """Split document at semantic boundaries.
        
        Args:
            document: Document to chunk.
            
        Returns:
            List of chunks.
        """
        if not self._sentence_transformer:
            # Fallback to character chunking if no model
            return CharacterChunker(chunk_size=500).chunk(document)
        
        try:
            return self._semantic_split(document)
        except Exception:
            # Fallback on error
            return CharacterChunker(chunk_size=500).chunk(document)
    
    def _semantic_split(self, document: Document) -> List[Chunk]:
        """Perform semantic split.
        
        Args:
            document: Document to split.
            
        Returns:
            List of semantic chunks.
        """
        # Split into sentences first
        sentences = self._split_sentences(document.content)
        
        if not sentences:
            return []
        
        # Get embeddings
        embeddings = self._sentence_transformer.encode(sentences)
        
        # Find break points based on similarity
        chunks_list = []
        current_chunk_sentences = [sentences[0]]
        current_chunk_sentences_text = sentences[0]
        
        for i in range(1, len(sentences)):
            # Calculate similarity to last sentence
            similarity = self._cosine_similarity(
                embeddings[i],
                embeddings[i-1]
            )
            
            if similarity < self.similarity_threshold:
                # Start new chunk
                chunk_text = " ".join(current_chunk_sentences)
                if chunk_text.strip():
                    chunks_list.append(chunk_text)
                current_chunk_sentences = [sentences[i]]
            else:
                # Add to current chunk
                current_chunk_sentences.append(sentences[i])
        
        # Add last chunk
        if current_chunk_sentences:
            chunk_text = " ".join(current_chunk_sentences)
            if chunk_text.strip():
                chunks_list.append(chunk_text)
        
        # Create chunk objects
        chunks = []
        for idx, chunk_text in enumerate(chunks_list):
            chunk = Chunk(
                content=chunk_text,
                document_id=document.doc_id,
                chunk_number=idx,
                metadata={
                    **document.metadata,
                    "chunking_strategy": "semantic",
                    "sentence_count": len(chunk_text.split('. ')),
                },
            )
            chunks.append(chunk)
        
        return chunks
    
    @staticmethod
    def _split_sentences(text: str) -> List[str]:
        """Split text into sentences.
        
        Args:
            text: Text to split.
            
        Returns:
            List of sentences.
        """
        # Simple sentence splitting
        import re
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if s.strip()]
    
    @staticmethod
    def _cosine_similarity(vec1, vec2) -> float:
        """Calculate cosine similarity between vectors.
        
        Args:
            vec1: First vector.
            vec2: Second vector.
            
        Returns:
            Similarity score (0-1).
        """
        import numpy as np
        
        vec1 = np.array(vec1)
        vec2 = np.array(vec2)
        
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
