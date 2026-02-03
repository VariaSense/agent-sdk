"""Persistence layer for storing vector embeddings and documents."""

import json
import os
import pickle
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from agent_sdk.data_connectors.document import Document, Chunk


class MemoryStore(ABC):
    """Abstract base class for vector memory persistence."""
    
    @abstractmethod
    async def save(self, document: Document, embedding: List[float]) -> None:
        """Save document with embedding.
        
        Args:
            document: Document to save.
            embedding: Vector embedding.
        """
        pass
    
    @abstractmethod
    async def load(self, doc_id: str) -> Optional[tuple]:
        """Load document and embedding by ID.
        
        Args:
            doc_id: Document ID.
            
        Returns:
            Tuple of (document, embedding) or None.
        """
        pass
    
    @abstractmethod
    async def delete(self, doc_id: str) -> bool:
        """Delete document by ID.
        
        Args:
            doc_id: Document ID.
            
        Returns:
            True if deleted, False if not found.
        """
        pass
    
    @abstractmethod
    async def list_all(self) -> List[str]:
        """List all document IDs.
        
        Returns:
            List of document IDs.
        """
        pass


class FileSystemStore(MemoryStore):
    """File system-based vector memory storage."""
    
    def __init__(self, base_dir: str = "./vector_store"):
        """Initialize filesystem store.
        
        Args:
            base_dir: Base directory for storage.
        """
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)
        
        self.documents_dir = os.path.join(base_dir, "documents")
        self.embeddings_dir = os.path.join(base_dir, "embeddings")
        
        os.makedirs(self.documents_dir, exist_ok=True)
        os.makedirs(self.embeddings_dir, exist_ok=True)
    
    def _get_doc_path(self, doc_id: str) -> str:
        """Get file path for document."""
        return os.path.join(self.documents_dir, f"{doc_id}.json")
    
    def _get_embedding_path(self, doc_id: str) -> str:
        """Get file path for embedding."""
        return os.path.join(self.embeddings_dir, f"{doc_id}.pkl")
    
    async def save(self, document: Document, embedding: List[float]) -> None:
        """Save document and embedding to files.
        
        Args:
            document: Document to save.
            embedding: Vector embedding.
        """
        # Save document as JSON
        doc_path = self._get_doc_path(document.doc_id)
        with open(doc_path, 'w') as f:
            json.dump(document.to_dict(), f, indent=2, default=str)
        
        # Save embedding as pickle
        emb_path = self._get_embedding_path(document.doc_id)
        with open(emb_path, 'wb') as f:
            pickle.dump(embedding, f)
    
    async def load(self, doc_id: str) -> Optional[tuple]:
        """Load document and embedding from files.
        
        Args:
            doc_id: Document ID.
            
        Returns:
            Tuple of (document, embedding) or None.
        """
        doc_path = self._get_doc_path(doc_id)
        emb_path = self._get_embedding_path(doc_id)
        
        if not os.path.exists(doc_path) or not os.path.exists(emb_path):
            return None
        
        try:
            # Load document
            with open(doc_path, 'r') as f:
                doc_data = json.load(f)
            document = Document(
                content=doc_data['content'],
                metadata=doc_data.get('metadata', {}),
                source=doc_data.get('source'),
                doc_id=doc_data.get('doc_id')
            )
            
            # Load embedding
            with open(emb_path, 'rb') as f:
                embedding = pickle.load(f)
            
            return (document, embedding)
        except Exception:
            return None
    
    async def delete(self, doc_id: str) -> bool:
        """Delete document and embedding files.
        
        Args:
            doc_id: Document ID.
            
        Returns:
            True if deleted.
        """
        doc_path = self._get_doc_path(doc_id)
        emb_path = self._get_embedding_path(doc_id)
        
        deleted = False
        if os.path.exists(doc_path):
            os.remove(doc_path)
            deleted = True
        if os.path.exists(emb_path):
            os.remove(emb_path)
            deleted = True
        
        return deleted
    
    async def list_all(self) -> List[str]:
        """List all document IDs.
        
        Returns:
            List of document IDs.
        """
        doc_ids = []
        for filename in os.listdir(self.documents_dir):
            if filename.endswith('.json'):
                doc_id = filename[:-5]  # Remove .json extension
                doc_ids.append(doc_id)
        
        return sorted(doc_ids)


class PostgresVectorStore(MemoryStore):
    """PostgreSQL with pgvector extension for vector storage."""
    
    def __init__(
        self,
        connection_string: str,
        table_name: str = "vector_store"
    ):
        """Initialize PostgreSQL vector store.
        
        Args:
            connection_string: PostgreSQL connection URL.
            table_name: Table name for storage.
        """
        self.connection_string = connection_string
        self.table_name = table_name
        
        try:
            import psycopg2
            self._psycopg2 = psycopg2
        except ImportError:
            raise ImportError("psycopg2 required for PostgresVectorStore")
    
    async def _get_connection(self):
        """Get database connection."""
        return self._psycopg2.connect(self.connection_string)
    
    async def _init_table(self) -> None:
        """Initialize vector store table."""
        conn = await self._get_connection()
        try:
            cur = conn.cursor()
            
            # Enable pgvector extension
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            
            # Create table
            create_table_sql = f"""
            CREATE TABLE IF NOT EXISTS {self.table_name} (
                doc_id TEXT PRIMARY KEY,
                document JSONB NOT NULL,
                embedding vector(1536),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
            cur.execute(create_table_sql)
            
            # Create index for fast similarity search
            cur.execute(f"""
            CREATE INDEX IF NOT EXISTS {self.table_name}_embedding_idx 
            ON {self.table_name} USING ivfflat (embedding vector_cosine_ops);
            """)
            
            conn.commit()
        finally:
            conn.close()
    
    async def save(self, document: Document, embedding: List[float]) -> None:
        """Save document and embedding to PostgreSQL.
        
        Args:
            document: Document to save.
            embedding: Vector embedding.
        """
        await self._init_table()
        
        conn = await self._get_connection()
        try:
            cur = conn.cursor()
            
            # Convert embedding list to pgvector format
            embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"
            
            insert_sql = f"""
            INSERT INTO {self.table_name} (doc_id, document, embedding)
            VALUES (%s, %s, %s::vector)
            ON CONFLICT (doc_id) DO UPDATE SET
                document = EXCLUDED.document,
                embedding = EXCLUDED.embedding;
            """
            
            cur.execute(insert_sql, (
                document.doc_id,
                json.dumps(document.to_dict(), default=str),
                embedding_str
            ))
            conn.commit()
        finally:
            conn.close()
    
    async def load(self, doc_id: str) -> Optional[tuple]:
        """Load document and embedding from PostgreSQL.
        
        Args:
            doc_id: Document ID.
            
        Returns:
            Tuple of (document, embedding) or None.
        """
        conn = await self._get_connection()
        try:
            cur = conn.cursor()
            
            select_sql = f"""
            SELECT document, embedding::text FROM {self.table_name}
            WHERE doc_id = %s;
            """
            
            cur.execute(select_sql, (doc_id,))
            result = cur.fetchone()
            
            if not result:
                return None
            
            doc_data, embedding_str = result
            
            # Parse embedding from pgvector format
            embedding = json.loads(embedding_str.strip('[]'))
            
            # Reconstruct document
            document = Document(
                content=doc_data['content'],
                metadata=doc_data.get('metadata', {}),
                source=doc_data.get('source'),
                doc_id=doc_data.get('doc_id')
            )
            
            return (document, embedding)
        finally:
            conn.close()
    
    async def delete(self, doc_id: str) -> bool:
        """Delete document from PostgreSQL.
        
        Args:
            doc_id: Document ID.
            
        Returns:
            True if deleted.
        """
        conn = await self._get_connection()
        try:
            cur = conn.cursor()
            
            delete_sql = f"DELETE FROM {self.table_name} WHERE doc_id = %s;"
            cur.execute(delete_sql, (doc_id,))
            
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()
    
    async def list_all(self) -> List[str]:
        """List all document IDs from PostgreSQL.
        
        Returns:
            List of document IDs.
        """
        conn = await self._get_connection()
        try:
            cur = conn.cursor()
            
            select_sql = f"SELECT doc_id FROM {self.table_name} ORDER BY doc_id;"
            cur.execute(select_sql)
            
            return [row[0] for row in cur.fetchall()]
        finally:
            conn.close()


class PineconeStore(MemoryStore):
    """Pinecone vector database storage."""
    
    def __init__(
        self,
        api_key: str,
        index_name: str = "documents",
        environment: str = "us-west1-gcp"
    ):
        """Initialize Pinecone store.
        
        Args:
            api_key: Pinecone API key.
            index_name: Pinecone index name.
            environment: Pinecone environment.
        """
        self.api_key = api_key
        self.index_name = index_name
        self.environment = environment
        
        try:
            import pinecone
            self._pinecone = pinecone
            self._pinecone.init(api_key=api_key, environment=environment)
        except ImportError:
            raise ImportError("pinecone-client required for PineconeStore")
    
    async def save(self, document: Document, embedding: List[float]) -> None:
        """Save document and embedding to Pinecone.
        
        Args:
            document: Document to save.
            embedding: Vector embedding.
        """
        index = self._pinecone.Index(self.index_name)
        
        # Prepare metadata
        metadata = {
            'content': document.content,
            'source': document.source or '',
            'metadata': json.dumps(document.metadata, default=str)
        }
        
        # Upsert to Pinecone
        index.upsert(
            vectors=[(document.doc_id, embedding, metadata)],
            namespace="default"
        )
    
    async def load(self, doc_id: str) -> Optional[tuple]:
        """Load document and embedding from Pinecone.
        
        Args:
            doc_id: Document ID.
            
        Returns:
            Tuple of (document, embedding) or None.
        """
        index = self._pinecone.Index(self.index_name)
        
        # Fetch from Pinecone
        result = index.fetch(ids=[doc_id], namespace="default")
        
        if not result.get('vectors'):
            return None
        
        vector_data = result['vectors'][doc_id]
        embedding = vector_data['values']
        metadata = vector_data.get('metadata', {})
        
        # Reconstruct document
        document = Document(
            content=metadata.get('content', ''),
            metadata=json.loads(metadata.get('metadata', '{}')),
            source=metadata.get('source'),
            doc_id=doc_id
        )
        
        return (document, embedding)
    
    async def delete(self, doc_id: str) -> bool:
        """Delete document from Pinecone.
        
        Args:
            doc_id: Document ID.
            
        Returns:
            True if deleted.
        """
        index = self._pinecone.Index(self.index_name)
        
        result = index.delete(ids=[doc_id], namespace="default")
        
        return result.get('deleted_count', 0) > 0
    
    async def list_all(self) -> List[str]:
        """List all document IDs from Pinecone.
        
        Returns:
            List of document IDs.
        """
        index = self._pinecone.Index(self.index_name)
        
        # Query to get all vectors (Pinecone has limited list support)
        doc_ids = []
        try:
            # Use describe_index_stats to get count
            stats = index.describe_index_stats()
            # Note: Full listing requires scanning - this is a simplified version
            # In production, would use pagination
        except Exception:
            pass
        
        return doc_ids
