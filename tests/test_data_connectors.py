"""Tests for document models and loaders."""

import pytest
import os
import json
import tempfile
from agent_sdk.data_connectors.document import Document, Chunk
from agent_sdk.data_connectors.pdf_loader import PDFLoader
from agent_sdk.data_connectors.structured_loader import CSVLoader, JSONLoader
from agent_sdk.data_connectors.web_scraper import WebScraper
from agent_sdk.data_connectors.database_adapter import (
    SQLiteAdapter,
    PostgresAdapter,
    MySQLAdapter,
)
from agent_sdk.data_connectors.chunking import (
    CharacterChunker,
    TokenChunker,
    SemanticChunker,
)


# Document Model Tests
class TestDocument:
    """Test Document model."""
    
    def test_document_creation(self):
        """Test creating a document."""
        doc = Document(
            content="Test content",
            metadata={"key": "value"},
            source="test.txt"
        )
        assert doc.content == "Test content"
        assert doc.metadata["key"] == "value"
        assert doc.source == "test.txt"
        assert doc.created_at is not None
    
    def test_document_default_doc_id(self):
        """Test default doc_id generation."""
        doc = Document(content="Test", source="file.txt")
        assert doc.doc_id is not None
        assert "doc_" in doc.doc_id
    
    def test_document_to_dict(self):
        """Test document serialization."""
        doc = Document(
            content="Test",
            metadata={"key": "value"},
            source="test.txt"
        )
        d = doc.to_dict()
        assert d["content"] == "Test"
        assert d["metadata"]["key"] == "value"
        assert d["source"] == "test.txt"
    
    def test_document_get_metadata(self):
        """Test getting metadata values."""
        doc = Document(
            content="Test",
            metadata={"key": "value"}
        )
        assert doc.get_metadata("key") == "value"
        assert doc.get_metadata("missing", "default") == "default"
    
    def test_document_to_text(self):
        """Test text extraction."""
        doc = Document(content="Test content")
        assert doc.to_text() == "Test content"


class TestChunk:
    """Test Chunk model."""
    
    def test_chunk_creation(self):
        """Test creating a chunk."""
        chunk = Chunk(
            content="Chunk content",
            document_id="doc_1",
            chunk_number=0,
        )
        assert chunk.content == "Chunk content"
        assert chunk.document_id == "doc_1"
        assert chunk.chunk_number == 0
    
    def test_chunk_id_generation(self):
        """Test chunk ID generation."""
        chunk = Chunk(
            content="Test",
            document_id="doc_1",
            chunk_number=2,
        )
        assert chunk.get_chunk_id() == "doc_1_2"
    
    def test_chunk_has_embedding(self):
        """Test embedding check."""
        chunk_no_embed = Chunk(
            content="Test",
            document_id="doc_1",
            chunk_number=0,
        )
        assert not chunk_no_embed.has_embedding()
        
        chunk_with_embed = Chunk(
            content="Test",
            document_id="doc_1",
            chunk_number=0,
            embedding=[0.1, 0.2, 0.3]
        )
        assert chunk_with_embed.has_embedding()
    
    def test_chunk_to_dict(self):
        """Test chunk serialization."""
        chunk = Chunk(
            content="Test",
            document_id="doc_1",
            chunk_number=0,
            metadata={"type": "body"}
        )
        d = chunk.to_dict()
        assert d["content"] == "Test"
        assert d["document_id"] == "doc_1"
        assert d["chunk_number"] == 0


# Loader Tests
class TestCSVLoader:
    """Test CSV loader."""
    
    def test_csv_load_simple(self):
        """Test loading simple CSV."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("name,age\nAlice,30\nBob,25\n")
            f.flush()
            
            try:
                loader = CSVLoader()
                docs = loader.load(f.name)
                
                assert len(docs) == 1
                assert "Alice" in docs[0].content or "name" in docs[0].content
                assert docs[0].metadata["total_rows"] == 2
                assert docs[0].metadata["total_columns"] == 2
            finally:
                os.unlink(f.name)
    
    def test_csv_file_not_found(self):
        """Test CSV loader with missing file."""
        loader = CSVLoader()
        with pytest.raises(FileNotFoundError):
            loader.load("/nonexistent/file.csv")


class TestJSONLoader:
    """Test JSON loader."""
    
    def test_json_load_object(self):
        """Test loading JSON object."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"name": "Alice", "age": 30}, f)
            f.flush()
            
            try:
                loader = JSONLoader()
                docs = loader.load(f.name)
                
                assert len(docs) == 1
                assert "Alice" in docs[0].content or "name" in docs[0].content
            finally:
                os.unlink(f.name)
    
    def test_json_load_array(self):
        """Test loading JSON array."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump([{"name": "Alice"}, {"name": "Bob"}], f)
            f.flush()
            
            try:
                loader = JSONLoader()
                docs = loader.load(f.name)
                
                assert len(docs) == 2
            finally:
                os.unlink(f.name)
    
    def test_json_invalid_file(self):
        """Test invalid JSON."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("{ invalid json }")
            f.flush()
            
            try:
                loader = JSONLoader()
                with pytest.raises(ValueError):
                    loader.load(f.name)
            finally:
                os.unlink(f.name)


# Chunking Tests
class TestCharacterChunker:
    """Test character-based chunking."""
    
    def test_character_chunking(self):
        """Test basic character chunking."""
        doc = Document(content="a" * 1000, source="test.txt")
        chunker = CharacterChunker(chunk_size=100, overlap=10)
        
        chunks = chunker.chunk(doc)
        
        assert len(chunks) > 0
        assert all(len(c.content) <= 110 for c in chunks)  # 100 + overlap
    
    def test_character_chunker_invalid_params(self):
        """Test invalid chunker parameters."""
        with pytest.raises(ValueError):
            CharacterChunker(chunk_size=0)
        
        with pytest.raises(ValueError):
            CharacterChunker(chunk_size=100, overlap=100)
    
    def test_character_chunker_empty_document(self):
        """Test chunking empty document."""
        doc = Document(content="", source="test.txt")
        chunker = CharacterChunker()
        
        chunks = chunker.chunk(doc)
        assert len(chunks) == 0


class TestTokenChunker:
    """Test token-based chunking."""
    
    def test_token_chunking(self):
        """Test token-based chunking."""
        doc = Document(
            content="The quick brown fox jumps over the lazy dog. " * 20,
            source="test.txt"
        )
        chunker = TokenChunker(max_tokens=50, overlap=5)
        
        chunks = chunker.chunk(doc)
        
        assert len(chunks) > 0
        assert all(isinstance(c, Chunk) for c in chunks)
    
    def test_token_chunker_invalid_params(self):
        """Test invalid parameters."""
        with pytest.raises(ValueError):
            TokenChunker(max_tokens=0)
    
    def test_token_chunker_empty_document(self):
        """Test chunking empty document."""
        doc = Document(content="", source="test.txt")
        chunker = TokenChunker()
        
        chunks = chunker.chunk(doc)
        assert len(chunks) == 0


class TestSemanticChunker:
    """Test semantic chunking."""
    
    def test_semantic_chunker_fallback(self):
        """Test semantic chunker fallback behavior."""
        doc = Document(
            content="First sentence. Second sentence. Third sentence.",
            source="test.txt"
        )
        # This will likely use fallback since sentence-transformers may not be installed
        chunker = SemanticChunker(similarity_threshold=0.5)
        
        chunks = chunker.chunk(doc)
        
        assert len(chunks) > 0
        assert all(isinstance(c, Chunk) for c in chunks)
    
    def test_semantic_chunker_invalid_threshold(self):
        """Test invalid similarity threshold."""
        with pytest.raises(ValueError):
            SemanticChunker(similarity_threshold=1.5)
        
        with pytest.raises(ValueError):
            SemanticChunker(similarity_threshold=-0.1)


class TestPDFLoader:
    """Test PDF loader."""
    
    def test_pdf_load_nonexistent(self):
        """Test loading non-existent PDF."""
        loader = PDFLoader()
        with pytest.raises(FileNotFoundError):
            loader.load("/nonexistent/file.pdf")
    
    def test_pdf_load_invalid_extension(self):
        """Test loading non-PDF file."""
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as f:
            f.write(b"Not a PDF")
            f.flush()
            
            try:
                loader = PDFLoader()
                with pytest.raises(ValueError, match="not a PDF"):
                    loader.load(f.name)
            finally:
                os.unlink(f.name)


class TestSQLiteAdapter:
    """Test SQLite adapter."""
    
    def test_sqlite_connect(self):
        """Test SQLite connection."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        try:
            adapter = SQLiteAdapter(db_path)
            assert adapter.connect()
            adapter.disconnect()
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)
    
    def test_sqlite_query(self):
        """Test SQLite query."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        try:
            adapter = SQLiteAdapter(db_path)
            adapter.connect()
            
            # Create table
            adapter.query("""
                CREATE TABLE users (
                    id INTEGER,
                    name TEXT
                )
            """)
            
            # Insert data
            adapter.query("INSERT INTO users VALUES (1, 'Alice')")
            
            # Query data
            results = adapter.query("SELECT * FROM users")
            assert len(results) == 1
            assert results[0]['name'] == 'Alice'
            
            adapter.disconnect()
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)


class TestDatabaseAdapterFactory:
    """Test database adapter factory methods."""
    
    def test_sqlite_factory(self):
        """Test SQLite factory."""
        adapter = SQLiteAdapter.create_for_sqlite(":memory:")
        assert isinstance(adapter, SQLiteAdapter)
    
    def test_postgres_factory(self):
        """Test PostgreSQL factory."""
        adapter = PostgresAdapter.create_for_postgres("postgresql://localhost/test")
        assert isinstance(adapter, PostgresAdapter)
    
    def test_mysql_factory(self):
        """Test MySQL factory."""
        adapter = MySQLAdapter.create_for_mysql("mysql://localhost/test")
        assert isinstance(adapter, MySQLAdapter)


class TestWebScraper:
    """Test web scraper."""
    
    def test_web_scraper_invalid_url(self):
        """Test scraper with invalid URL."""
        scraper = WebScraper()
        with pytest.raises(ValueError, match="Invalid URL"):
            scraper.scrape_url("not_a_url")
    
    def test_web_scraper_extract_links_invalid_url(self):
        """Test link extraction with invalid URL."""
        scraper = WebScraper()
        with pytest.raises(ValueError, match="Invalid URL"):
            scraper.extract_links("not_a_url")
    
    def test_web_scraper_extract_links_no_network(self):
        """Test that extraction handles network errors gracefully."""
        scraper = WebScraper()
        links = scraper.extract_links("https://this_domain_definitely_does_not_exist.test")
        # Should return empty list on error
        assert isinstance(links, list)
