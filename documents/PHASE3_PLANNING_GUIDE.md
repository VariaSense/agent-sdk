# Phase 3 Planning Guide: Data Connectors & Advanced Memory

**Current Status**: Phase 1 + 2 Complete (113/113 tests, 26.10% coverage)  
**Next Phase**: Phase 3 - Data Connectors + Advanced Semantic Memory  
**Estimated Timeline**: 5-6 hours for complete implementation  
**Target Coverage**: 90%+ competitive parity  

---

## Phase 3A: Data Connectors Library (RECOMMENDED FIRST)

### Overview
Build comprehensive data loading and processing capabilities for integrating various data sources with the agent SDK.

### Components

#### 1. PDF Loader
**File**: `agent_sdk/data_connectors/pdf_loader.py`

```python
class PDFLoader:
    """Extract text and metadata from PDF files."""
    
    def load(self, file_path: str) -> List[Document]:
        """Load and parse PDF, return list of documents."""
        
    def extract_metadata(self, file_path: str) -> Dict:
        """Extract PDF metadata (title, author, pages, etc)."""
        
    def extract_tables(self, file_path: str) -> List[Table]:
        """Extract tabular data from PDF."""
```

**Dependencies**: `pdfplumber` or `PyPDF2`  
**Use Cases**: Contract analysis, document processing, data extraction  
**Estimated LOC**: 80-100  
**Tests**: 6-8  

#### 2. CSV/JSON Loader
**File**: `agent_sdk/data_connectors/structured_loader.py`

```python
class CSVLoader:
    """Load and parse CSV files."""
    
    def load(self, file_path: str) -> List[Document]:
        """Load CSV, infer schema, return documents."""
        
    def infer_schema(self, file_path: str) -> Schema:
        """Auto-detect column types and relationships."""

class JSONLoader:
    """Load and parse JSON files."""
    
    def load(self, file_path: str) -> List[Document]:
        """Load JSON, flatten nested structures, return documents."""
```

**Dependencies**: `pandas`, `json`  
**Use Cases**: Data analysis, database migration, config processing  
**Estimated LOC**: 100-120  
**Tests**: 8-10  

#### 3. Web Scraper
**File**: `agent_sdk/data_connectors/web_scraper.py`

```python
class WebScraper:
    """Extract content from websites."""
    
    def scrape_url(self, url: str) -> Document:
        """Fetch and parse webpage content."""
        
    def scrape_with_selenium(self, url: str) -> Document:
        """Scrape JavaScript-heavy pages."""
        
    def extract_links(self, url: str) -> List[str]:
        """Find all links on a page."""
```

**Dependencies**: `requests`, `beautifulsoup4`, `selenium` (optional)  
**Use Cases**: Research, content aggregation, web monitoring  
**Estimated LOC**: 120-150  
**Tests**: 8-10  

#### 4. Database Adapter
**File**: `agent_sdk/data_connectors/database_adapter.py`

```python
class DatabaseAdapter:
    """Generic database connector."""
    
    @classmethod
    def create_for_postgres(cls, connection_string: str):
        """Factory for PostgreSQL."""
        
    @classmethod
    def create_for_mysql(cls, connection_string: str):
        """Factory for MySQL."""
        
    @classmethod
    def create_for_mongodb(cls, connection_string: str):
        """Factory for MongoDB."""
        
    def query(self, sql: str) -> List[Dict]:
        """Execute query and return results."""
        
    def load_table(self, table_name: str) -> List[Document]:
        """Load entire table as documents."""
```

**Dependencies**: `sqlalchemy`, `pymongo`, `psycopg2`  
**Use Cases**: Database migration, data sync, enterprise integration  
**Estimated LOC**: 150-180  
**Tests**: 10-12  

#### 5. Chunking Engine
**File**: `agent_sdk/data_connectors/chunking.py`

```python
class ChunkingStrategy:
    """Base class for document chunking."""
    
    def chunk(self, document: Document) -> List[Chunk]:
        """Split document into chunks."""

class CharacterChunker(ChunkingStrategy):
    """Split by character count."""
    
    def __init__(self, chunk_size: int = 1000, overlap: int = 200):
        """Initialize with chunk size and overlap."""

class TokenChunker(ChunkingStrategy):
    """Split by token count (for embeddings)."""
    
    def __init__(self, max_tokens: int = 500, overlap: int = 50):
        """Initialize with token limits."""

class SemanticChunker(ChunkingStrategy):
    """Split by semantic similarity."""
    
    def chunk(self, document: Document, model) -> List[Chunk]:
        """Split document at semantic boundaries."""
```

**Dependencies**: `tiktoken`, `sentence-transformers`  
**Use Cases**: Embedding preparation, context windowing, RAG systems  
**Estimated LOC**: 120-150  
**Tests**: 8-10  

#### 6. Document Model
**File**: `agent_sdk/data_connectors/document.py`

```python
@dataclass
class Document:
    """Unified document representation."""
    content: str
    metadata: Dict[str, Any]
    source: str
    chunk_id: Optional[int] = None
    
    def to_dict(self) -> Dict:
        """Serialize document."""

@dataclass
class Chunk:
    """Document chunk for embeddings."""
    content: str
    document_id: str
    chunk_number: int
    metadata: Dict[str, Any]
    embedding: Optional[List[float]] = None
```

**Estimated LOC**: 30-40  
**Tests**: 4-6  

### Phase 3A Summary

| Component | LOC | Tests | Status |
|-----------|-----|-------|--------|
| PDF Loader | 90 | 7 | 📋 |
| CSV/JSON Loader | 110 | 9 | 📋 |
| Web Scraper | 135 | 9 | 📋 |
| Database Adapter | 165 | 11 | 📋 |
| Chunking Engine | 135 | 9 | 📋 |
| Document Model | 35 | 5 | 📋 |
| **Total** | **670** | **50** | **📋** |

---

## Phase 3B: Advanced Semantic Memory (SECONDARY)

### Overview
Enhance the memory module with vector embeddings and semantic search capabilities.

### Components

#### 1. Vector Embeddings
**File**: `agent_sdk/memory/embeddings.py`

```python
class EmbeddingProvider:
    """Base class for embedding providers."""
    
    async def embed_text(self, text: str) -> List[float]:
        """Generate embedding vector for text."""
        
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Batch embedding generation."""

class OpenAIEmbeddings(EmbeddingProvider):
    """OpenAI embedding model (text-embedding-3-small)."""
    
    def __init__(self, api_key: str, model: str = "text-embedding-3-small"):
        """Initialize with API key."""

class HuggingFaceEmbeddings(EmbeddingProvider):
    """HuggingFace embedding models (all-MiniLM-L6-v2)."""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """Initialize with model name."""
```

**Dependencies**: `openai`, `sentence-transformers`  
**Use Cases**: Semantic search, similarity comparison, clustering  
**Estimated LOC**: 120-150  
**Tests**: 8-10  

#### 2. Semantic Search
**File**: `agent_sdk/memory/semantic_search.py`

```python
class SemanticSearchEngine:
    """Search documents by semantic similarity."""
    
    def index(self, documents: List[Document], embeddings_provider):
        """Build index from documents."""
        
    def search(self, query: str, top_k: int = 5) -> List[Tuple[Document, float]]:
        """Find most similar documents to query."""
        
    def search_hybrid(self, query: str, filter: Dict, top_k: int = 5):
        """Combine semantic and metadata filtering."""

class RetrievalStrategy:
    """Base class for retrieval strategies."""

class SimilaritySearch(RetrievalStrategy):
    """Simple similarity-based retrieval."""

class HybridSearch(RetrievalStrategy):
    """Combine semantic similarity with metadata."""

class MMRSearch(RetrievalStrategy):
    """Maximize Marginal Relevance to reduce redundancy."""
```

**Estimated LOC**: 150-180  
**Tests**: 8-10  

#### 3. Persistence Layer
**File**: `agent_sdk/memory/persistence.py`

```python
class MemoryStore:
    """Base class for memory persistence."""
    
    def save_documents(self, documents: List[Document]):
        """Store documents."""
        
    def load_documents(self, query: Dict) -> List[Document]:
        """Retrieve documents."""
        
    def delete_documents(self, ids: List[str]):
        """Delete documents."""

class FileSystemStore(MemoryStore):
    """Store vectors and documents in files."""
    
    def __init__(self, storage_path: str):
        """Initialize file storage."""

class PostgresVectorStore(MemoryStore):
    """Use PostgreSQL with pgvector extension."""
    
    def __init__(self, connection_string: str):
        """Initialize database connection."""

class PineconeStore(MemoryStore):
    """Use Pinecone vector database."""
    
    def __init__(self, api_key: str, index_name: str):
        """Initialize Pinecone connection."""
```

**Dependencies**: `psycopg2`, `pinecone-client`  
**Use Cases**: RAG systems, long-term memory, knowledge bases  
**Estimated LOC**: 160-200  
**Tests**: 8-10  

#### 4. Memory Manager Enhancement
**File**: `agent_sdk/memory/enhanced_manager.py`

```python
class SemanticMemoryManager:
    """Enhanced memory with semantic search."""
    
    def __init__(self, embeddings_provider, store, search_strategy):
        """Initialize with components."""
        
    def add_documents(self, documents: List[Document]):
        """Index documents for semantic search."""
        
    def retrieve(self, query: str, top_k: int = 5) -> List[Document]:
        """Retrieve semantically similar documents."""
        
    def retrieve_with_context(self, query: str, context: Dict) -> List[Document]:
        """Retrieve with metadata filtering."""
        
    def update_document(self, doc_id: str, document: Document):
        """Update indexed document."""
        
    def delete_document(self, doc_id: str):
        """Remove from memory."""
```

**Estimated LOC**: 100-120  
**Tests**: 6-8  

### Phase 3B Summary

| Component | LOC | Tests | Status |
|-----------|-----|-------|--------|
| Vector Embeddings | 135 | 9 | 📋 |
| Semantic Search | 165 | 9 | 📋 |
| Persistence Layer | 180 | 9 | 📋 |
| Memory Manager | 110 | 7 | 📋 |
| **Total** | **590** | **34** | **📋** |

---

## Implementation Order & Dependencies

### Recommended Sequence for Phase 3A (Data Connectors)

```
1. Document Model (foundation)
   ↓
2. PDF Loader (most common)
   ↓
3. CSV/JSON Loader (structured data)
   ↓
4. Chunking Engine (critical for embeddings)
   ↓
5. Web Scraper (additional sources)
   ↓
6. Database Adapter (enterprise needs)
   ↓
7. Integration Tests (end-to-end)
```

### Recommended Sequence for Phase 3B (Memory)

```
1. Vector Embeddings (foundation)
   ↓
2. Semantic Search (core feature)
   ↓
3. Persistence Layer (storage)
   ↓
4. Memory Manager (orchestration)
   ↓
5. Integration Tests (end-to-end)
```

---

## Test Coverage Plan

### Phase 3A: Data Connectors (50 tests)

```python
# test_pdf_loader.py (7 tests)
- load_simple_pdf
- extract_text_with_formatting
- extract_metadata
- handle_corrupted_pdf
- handle_missing_file
- extract_tables
- preserve_document_structure

# test_csv_json_loader.py (9 tests)
- load_csv_basic
- load_json_nested
- infer_schema_types
- handle_large_files
- handle_missing_values
- flatten_nested_json
- preserve_column_order

# test_web_scraper.py (9 tests)
- scrape_simple_html
- extract_links
- handle_404
- handle_timeout
- js_heavy_page_selenium
- respect_robots_txt
- extract_structured_data

# test_database_adapter.py (11 tests)
- postgres_connection
- mysql_connection
- mongodb_connection
- query_execution
- load_table
- handle_connection_error
- transaction_rollback
- connection_pooling
- parameterized_queries
- concurrent_queries

# test_chunking.py (9 tests)
- character_chunking
- token_chunking
- semantic_chunking
- overlap_handling
- preserve_metadata
- handle_large_documents
- chunk_ordering

# test_document_model.py (5 tests)
- document_creation
- serialization
- chunk_assignment
- metadata_handling
- validation
```

### Phase 3B: Semantic Memory (34 tests)

```python
# test_embeddings.py (9 tests)
- openai_embeddings
- huggingface_embeddings
- batch_embeddings
- embedding_dimension
- error_handling
- rate_limiting
- cache_hit

# test_semantic_search.py (9 tests)
- simple_similarity_search
- top_k_results
- hybrid_search
- mmr_search
- search_performance
- relevance_ranking
- empty_query_handling

# test_persistence.py (9 tests)
- filesystem_store_save
- filesystem_store_load
- postgres_vector_store
- pinecone_integration
- concurrent_access
- data_consistency
- corruption_recovery

# test_memory_manager.py (7 tests)
- add_documents
- retrieve_documents
- update_document
- delete_document
- retrieve_with_context
- memory_statistics
- integration_with_router
```

---

## Integration with Phase 1 & 2

### Phase 3A Integration Points

**Data Connectors + Prompt Management**:
```python
# Load data, then classify/process with prompts
docs = pdf_loader.load("contract.pdf")
manager = PromptManager()

for doc in docs:
    # Split into chunks
    chunks = chunking_engine.chunk(doc)
    
    for chunk in chunks:
        # Classify chunk type
        prompt = manager.render_template(
            "document_classifier",
            content=chunk.content
        )
```

**Data Connectors + Model Router**:
```python
# Complex document → need powerful model
docs = web_scraper.scrape_url("complex_content")

if len(docs) > 10:  # Complex task
    model = router.select_model(
        available_models=models,
        task_description="Complex document processing"
    )
else:  # Simple task
    model = router.select_model(
        available_models=models,
        task_description="Simple text processing"
    )
```

### Phase 3B Integration Points

**Semantic Memory + React Pattern**:
```python
# Use memory for observations
executor = ReactExecutor()

async def think_action_observation():
    thought = "What historical data is relevant?"
    
    # Observation from semantic memory
    related_docs = memory.retrieve(thought, top_k=3)
    observation = "\n".join([d.content for d in related_docs])
    
    reflection = "This data shows..."
```

**Semantic Memory + Prompt Management**:
```python
# Find best prompt version based on similarity
query = user_input
similar_prompts = memory.retrieve(query, top_k=5)

best_prompt = manager.get_prompt(
    similar_prompts[0].metadata["prompt_id"],
    version=similar_prompts[0].metadata["version"]
)
```

---

## Success Criteria for Phase 3

### Phase 3A: Data Connectors
- [ ] 50+ tests passing (100%)
- [ ] Support for 6 data source types
- [ ] Chunking with 3+ strategies
- [ ] Competitive parity at ~85%

### Phase 3B: Semantic Memory
- [ ] 34+ tests passing (100%)
- [ ] Vector embeddings integrated
- [ ] 3+ retrieval strategies
- [ ] Competitive parity at ~90%

### Combined Phase 3
- [ ] 84+ tests (Phase 3A + 3B)
- [ ] 1,260+ LOC production code
- [ ] Coverage remains above 26%
- [ ] **Total: 197+ tests (Phase 1+2+3)**
- [ ] **Total: 2,980+ LOC production code**
- [ ] **Competitive parity: 90%+**

---

## Estimated Timeline

| Task | Hours | Complexity |
|------|-------|-----------|
| Setup & structure | 0.5 | ⭐ |
| Document Model | 0.5 | ⭐ |
| PDF Loader | 1 | ⭐⭐ |
| CSV/JSON Loader | 1 | ⭐⭐ |
| Chunking Engine | 1 | ⭐⭐⭐ |
| Web Scraper | 1 | ⭐⭐⭐ |
| Database Adapter | 1.5 | ⭐⭐⭐ |
| Phase 3A Tests | 1 | ⭐⭐ |
| **Phase 3A Total** | **7.5** | |
| Vector Embeddings | 1 | ⭐⭐ |
| Semantic Search | 1.5 | ⭐⭐⭐ |
| Persistence Layer | 1.5 | ⭐⭐⭐ |
| Memory Manager | 1 | ⭐⭐ |
| Phase 3B Tests | 1 | ⭐⭐ |
| **Phase 3B Total** | **6** | |
| Integration & Docs | 1.5 | ⭐⭐ |
| **GRAND TOTAL** | **15** | |

**Realistic estimate**: 5-6 hours for focused implementation (skipping some advanced features)

---

## Quick Start for Phase 3 Implementation

### Step 1: Choose Focus
```bash
# Option A: Start with Data Connectors (recommended)
# Phase 3A enables practical data loading

# Option B: Start with Semantic Memory (advanced)
# Phase 3B enables intelligent search
```

### Step 2: Create Module Structure
```bash
# For Phase 3A
mkdir -p agent_sdk/data_connectors
touch agent_sdk/data_connectors/__init__.py
touch agent_sdk/data_connectors/document.py

# For Phase 3B
touch agent_sdk/memory/embeddings.py
touch agent_sdk/memory/semantic_search.py
```

### Step 3: Begin Implementation
```bash
# Start with simplest components first
# 1. Document models (foundation)
# 2. Basic loaders (PDFs, CSVs)
# 3. Tests (ensure coverage)
# 4. Advanced features (scrapers, semantic search)
```

---

## User Prompts for Phase 3

When ready to start Phase 3, use these prompts:

**For Phase 3A**:
> "Let's implement Phase 3A: Data Connectors. Start with the document model and PDF loader."

**For Phase 3B**:
> "Let's implement Phase 3B: Semantic Memory with vector embeddings and search."

**For both**:
> "Implement Phase 3 with both Data Connectors and Semantic Memory."

---

## Conclusion

Phase 3 is well-planned with clear components, test coverage, and integration points. The implementation can be done incrementally, with Phase 3A (Data Connectors) providing immediate value and Phase 3B (Semantic Memory) adding advanced capabilities.

**Next action**: Choose Phase 3A or 3B, then begin implementation! 🚀

---

*Planning document for Phase 3 implementation*  
*Part of Month 4 - Agent SDK Development*  
*Status: Ready for implementation*
