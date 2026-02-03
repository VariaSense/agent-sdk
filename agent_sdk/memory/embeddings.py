"""Vector embedding providers for semantic search."""

from abc import ABC, abstractmethod
from typing import List, Optional
import os


class EmbeddingProvider(ABC):
    """Base class for embedding providers."""
    
    @property
    @abstractmethod
    def embedding_dimension(self) -> int:
        """Get dimension of embeddings produced by this provider.
        
        Returns:
            Dimension of embedding vectors.
        """
        pass
    
    @abstractmethod
    async def embed_text(self, text: str) -> List[float]:
        """Generate embedding vector for text.
        
        Args:
            text: Text to embed.
            
        Returns:
            Embedding vector.
        """
        pass
    
    @abstractmethod
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts.
        
        Args:
            texts: List of texts to embed.
            
        Returns:
            List of embedding vectors.
        """
        pass
    
    def embed_text_sync(self, text: str) -> List[float]:
        """Synchronous wrapper for embed_text.
        
        Args:
            text: Text to embed.
            
        Returns:
            Embedding vector.
        """
        import asyncio
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.embed_text(text))
        finally:
            loop.close()
    
    def embed_batch_sync(self, texts: List[str]) -> List[List[float]]:
        """Synchronous wrapper for embed_batch.
        
        Args:
            texts: Texts to embed.
            
        Returns:
            List of embedding vectors.
        """
        import asyncio
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.embed_batch(texts))
        finally:
            loop.close()


class OpenAIEmbeddings(EmbeddingProvider):
    """OpenAI embedding model (text-embedding-3-small)."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "text-embedding-3-small"):
        """Initialize OpenAI embeddings.
        
        Args:
            api_key: OpenAI API key (or OPENAI_API_KEY environment variable).
            model: Model to use (text-embedding-3-small or text-embedding-3-large).
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self._client = None
        self._dimension = 1536 if "small" in model else 3072
    
    @property
    def embedding_dimension(self) -> int:
        """Get embedding dimension."""
        return self._dimension
    
    async def embed_text(self, text: str) -> List[float]:
        """Generate embedding for text.
        
        Args:
            text: Text to embed.
            
        Returns:
            Embedding vector.
        """
        try:
            from openai import AsyncOpenAI
            
            if not self._client:
                self._client = AsyncOpenAI(api_key=self.api_key)
            
            response = await self._client.embeddings.create(
                model=self.model,
                input=text
            )
            
            return response.data[0].embedding
        except ImportError:
            raise ImportError("openai package required: pip install openai")
        except Exception as e:
            raise RuntimeError(f"OpenAI embedding failed: {str(e)}")
    
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts.
        
        Args:
            texts: Texts to embed.
            
        Returns:
            List of embeddings.
        """
        try:
            from openai import AsyncOpenAI
            
            if not self._client:
                self._client = AsyncOpenAI(api_key=self.api_key)
            
            response = await self._client.embeddings.create(
                model=self.model,
                input=texts
            )
            
            # Sort by index to maintain order
            embeddings_dict = {item.index: item.embedding for item in response.data}
            return [embeddings_dict[i] for i in range(len(texts))]
        except ImportError:
            raise ImportError("openai package required: pip install openai")
        except Exception as e:
            raise RuntimeError(f"OpenAI embedding failed: {str(e)}")


class HuggingFaceEmbeddings(EmbeddingProvider):
    """HuggingFace embedding models (all-MiniLM-L6-v2 by default)."""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """Initialize HuggingFace embeddings.
        
        Args:
            model_name: Model name from HuggingFace (e.g., all-MiniLM-L6-v2).
        """
        self.model_name = model_name
        self._model = None
        self._dimension = None
    
    def _load_model(self):
        """Load embedding model."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                
                self._model = SentenceTransformer(self.model_name)
                # Get dimension from model
                self._dimension = self._model.get_sentence_embedding_dimension()
            except ImportError:
                raise ImportError("sentence-transformers required: pip install sentence-transformers")
            except Exception as e:
                raise RuntimeError(f"Failed to load model {self.model_name}: {str(e)}")
    
    @property
    def embedding_dimension(self) -> int:
        """Get embedding dimension."""
        if self._dimension is None:
            self._load_model()
        return self._dimension
    
    async def embed_text(self, text: str) -> List[float]:
        """Generate embedding for text.
        
        Args:
            text: Text to embed.
            
        Returns:
            Embedding vector.
        """
        if self._model is None:
            self._load_model()
        
        embedding = self._model.encode(text, convert_to_tensor=False)
        return embedding.tolist()
    
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts.
        
        Args:
            texts: Texts to embed.
            
        Returns:
            List of embeddings.
        """
        if self._model is None:
            self._load_model()
        
        embeddings = self._model.encode(texts, convert_to_tensor=False)
        return embeddings.tolist()


class LocalEmbeddings(EmbeddingProvider):
    """Local embedding provider using transformers."""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """Initialize local embeddings.
        
        Args:
            model_name: Local model name.
        """
        # Delegate to HuggingFace for now
        self.hf = HuggingFaceEmbeddings(model_name)
    
    @property
    def embedding_dimension(self) -> int:
        """Get embedding dimension."""
        return self.hf.embedding_dimension
    
    async def embed_text(self, text: str) -> List[float]:
        """Generate embedding for text.
        
        Args:
            text: Text to embed.
            
        Returns:
            Embedding vector.
        """
        return await self.hf.embed_text(text)
    
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts.
        
        Args:
            texts: Texts to embed.
            
        Returns:
            List of embeddings.
        """
        return await self.hf.embed_batch(texts)
