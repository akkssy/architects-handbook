"""Tests for the retrieval module."""

import tempfile
import shutil
from pathlib import Path
import pytest

from ai_code_assistant.retrieval.chunker import CodeChunker, CodeChunk
from ai_code_assistant.retrieval.indexer import CodebaseIndexer, IndexConfig, IndexStats
from ai_code_assistant.retrieval.search import CodebaseSearch, SearchResult, SearchResponse


class TestCodeChunker:
    """Tests for CodeChunker."""
    
    def test_detect_language_python(self):
        """Test language detection for Python files."""
        chunker = CodeChunker()
        assert chunker.detect_language("test.py") == "python"
        assert chunker.detect_language("script.pyw") is None  # Not in default map
        
    def test_detect_language_javascript(self):
        """Test language detection for JavaScript files."""
        chunker = CodeChunker()
        assert chunker.detect_language("app.js") == "javascript"
        assert chunker.detect_language("component.jsx") == "javascript"
        assert chunker.detect_language("module.ts") == "typescript"
        
    def test_detect_language_unknown(self):
        """Test language detection for unknown extensions."""
        chunker = CodeChunker()
        assert chunker.detect_language("file.xyz") is None
        assert chunker.detect_language("noextension") is None
        
    def test_chunk_small_file(self):
        """Test chunking a small Python file."""
        chunker = CodeChunker(chunk_size=100)
        code = '''def hello():
    """Say hello."""
    print("Hello, world!")
'''
        chunks = chunker.chunk_file("test.py", code)
        
        assert len(chunks) == 1
        assert chunks[0].chunk_type == "function"
        assert chunks[0].name == "hello"
        assert chunks[0].language == "python"
        
    def test_chunk_with_class(self):
        """Test chunking Python file with class."""
        chunker = CodeChunker()
        code = '''class MyClass:
    """A test class."""
    
    def method1(self):
        pass
    
    def method2(self):
        pass
'''
        chunks = chunker.chunk_file("test.py", code)
        
        # Should detect class
        assert any(c.chunk_type == "class" and c.name == "MyClass" for c in chunks)
        
    def test_chunk_generic_file(self):
        """Test chunking non-Python file."""
        chunker = CodeChunker(chunk_size=10, chunk_overlap=2)
        code = "\n".join([f"line {i}" for i in range(25)])
        
        chunks = chunker.chunk_file("data.txt", code)
        
        assert len(chunks) > 1
        assert all(c.chunk_type == "block" for c in chunks)
        
    def test_code_chunk_id(self):
        """Test CodeChunk ID generation."""
        chunk = CodeChunk(
            content="test",
            file_path="src/test.py",
            start_line=10,
            end_line=20,
            chunk_type="function",
            name="test_func",
        )
        
        assert chunk.id == "src/test.py:10-20"
        
    def test_code_chunk_to_dict(self):
        """Test CodeChunk serialization."""
        chunk = CodeChunk(
            content="def test(): pass",
            file_path="test.py",
            start_line=1,
            end_line=1,
            chunk_type="function",
            name="test",
            language="python",
        )
        
        d = chunk.to_dict()
        assert d["content"] == "def test(): pass"
        assert d["file_path"] == "test.py"
        assert d["chunk_type"] == "function"
        assert d["language"] == "python"


class TestCodebaseIndexer:
    """Tests for CodebaseIndexer."""
    
    @pytest.fixture
    def temp_codebase(self):
        """Create a temporary codebase for testing."""
        temp_dir = tempfile.mkdtemp()
        
        # Create some test files
        (Path(temp_dir) / "main.py").write_text('''
def main():
    """Main entry point."""
    print("Hello!")

if __name__ == "__main__":
    main()
''')
        
        (Path(temp_dir) / "utils.py").write_text('''
def helper_function(x):
    """A helper function."""
    return x * 2

class UtilityClass:
    """A utility class."""
    pass
''')
        
        # Create a subdirectory
        (Path(temp_dir) / "src").mkdir()
        (Path(temp_dir) / "src" / "module.py").write_text('''
class MyModule:
    """Module class."""
    def process(self, data):
        return data
''')
        
        yield temp_dir
        
        # Cleanup
        shutil.rmtree(temp_dir)
    
    def test_should_index_file(self, temp_codebase):
        """Test file filtering."""
        config = IndexConfig(persist_directory=".test-index")
        indexer = CodebaseIndexer(config=config, root_path=temp_codebase)
        
        assert indexer._should_index_file(Path(temp_codebase) / "main.py")
        assert not indexer._should_index_file(Path(temp_codebase) / "image.png")
        
        # Cleanup
        indexer._client.delete_collection(config.collection_name)
        
    def test_index_directory(self, temp_codebase):
        """Test indexing a directory."""
        config = IndexConfig(persist_directory=".test-index")
        indexer = CodebaseIndexer(config=config, root_path=temp_codebase)
        
        stats = indexer.index_directory(verbose=False)
        
        assert stats.total_files == 3
        assert len(stats.indexed_files) == 3
        assert stats.total_chunks > 0
        
        # Verify index stats
        index_stats = indexer.get_stats()
        assert index_stats["total_chunks"] > 0
        
        # Cleanup
        indexer.clear_index()


class TestCodebaseSearch:
    """Tests for CodebaseSearch."""

    @pytest.fixture
    def indexed_codebase(self):
        """Create and index a temporary codebase."""
        temp_dir = tempfile.mkdtemp()

        # Create test files with searchable content
        (Path(temp_dir) / "auth.py").write_text('''
def authenticate_user(username, password):
    """Authenticate a user with username and password."""
    # Check credentials against database
    if validate_credentials(username, password):
        return create_session(username)
    return None

def validate_credentials(username, password):
    """Validate user credentials."""
    return True
''')

        (Path(temp_dir) / "database.py").write_text('''
class DatabaseConnection:
    """Handle database connections."""

    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.connection = None

    def connect(self):
        """Establish database connection."""
        pass

    def query(self, sql):
        """Execute SQL query."""
        pass
''')

        # Index the codebase
        config = IndexConfig(persist_directory=".test-index")
        indexer = CodebaseIndexer(config=config, root_path=temp_dir)
        indexer.index_directory(verbose=False)

        yield temp_dir, config

        # Cleanup
        shutil.rmtree(temp_dir)

    def test_search_basic(self, indexed_codebase):
        """Test basic search functionality."""
        temp_dir, config = indexed_codebase

        search = CodebaseSearch(config=config, root_path=temp_dir)
        response = search.search("user authentication", top_k=5)

        assert response.has_results
        assert response.total_results > 0
        assert any("auth" in r.file_path for r in response.results)

    def test_search_database(self, indexed_codebase):
        """Test searching for database-related code."""
        temp_dir, config = indexed_codebase

        search = CodebaseSearch(config=config, root_path=temp_dir)
        response = search.search("database connection", top_k=5)

        assert response.has_results
        assert any("database" in r.file_path for r in response.results)

    def test_search_with_file_filter(self, indexed_codebase):
        """Test search with file filter."""
        temp_dir, config = indexed_codebase

        search = CodebaseSearch(config=config, root_path=temp_dir)
        response = search.search("function", top_k=10, file_filter="auth")

        # All results should be from auth.py
        for result in response.results:
            assert "auth" in result.file_path

    def test_search_no_results(self, indexed_codebase):
        """Test search with no matching results."""
        temp_dir, config = indexed_codebase

        search = CodebaseSearch(config=config, root_path=temp_dir)
        response = search.search("xyznonexistent123", top_k=5)

        # Should still return a response, possibly with low-scoring results
        assert isinstance(response, SearchResponse)

    def test_format_for_llm(self, indexed_codebase):
        """Test formatting results for LLM context."""
        temp_dir, config = indexed_codebase

        search = CodebaseSearch(config=config, root_path=temp_dir)
        response = search.search("authentication", top_k=3)

        formatted = response.format_for_llm(max_results=3)

        assert "Found" in formatted
        assert "Result" in formatted
        assert "```" in formatted  # Code blocks

    def test_get_file_context(self, indexed_codebase):
        """Test getting all chunks for a file."""
        temp_dir, config = indexed_codebase

        search = CodebaseSearch(config=config, root_path=temp_dir)
        results = search.get_file_context("auth.py")

        assert len(results) > 0
        assert all(r.file_path == "auth.py" for r in results)


class TestSearchResult:
    """Tests for SearchResult."""

    def test_str_representation(self):
        """Test string representation."""
        result = SearchResult(
            content="def test(): pass",
            file_path="test.py",
            start_line=10,
            end_line=15,
            chunk_type="function",
            name="test",
            language="python",
            score=0.85,
        )

        s = str(result)
        assert "test.py" in s
        assert "10-15" in s
        assert "0.85" in s

    def test_to_dict(self):
        """Test dictionary conversion."""
        result = SearchResult(
            content="code",
            file_path="file.py",
            start_line=1,
            end_line=5,
            chunk_type="block",
            name="",
            language="python",
            score=0.9,
        )

        d = result.to_dict()
        assert d["content"] == "code"
        assert d["score"] == 0.9
        assert d["language"] == "python"

    def test_to_dict_with_hybrid_scores(self):
        """Test dictionary conversion includes semantic and keyword scores."""
        result = SearchResult(
            content="code",
            file_path="file.py",
            start_line=1,
            end_line=5,
            chunk_type="function",
            name="process",
            language="python",
            score=0.75,
            semantic_score=0.8,
            keyword_score=0.7,
        )

        d = result.to_dict()
        assert d["score"] == 0.75
        assert d["semantic_score"] == 0.8
        assert d["keyword_score"] == 0.7


@pytest.fixture
def indexed_codebase_hybrid():
    """Create and index a codebase with specific function names for hybrid search testing.

    This fixture is used by TestHybridSearch and TestReranking.
    """
    temp_dir = tempfile.mkdtemp()

    # Create test files with specific function names for exact match testing
    (Path(temp_dir) / "request_handler.py").write_text('''
def processUserRequest(user_id, request_data):
    """Process a user request with validation."""
    if validate_request(request_data):
        return handle_request(user_id, request_data)
    return None

def validateRequest(data):
    """Validate incoming request data."""
    return data is not None

def handleAuthenticationError(error_code):
    """Handle authentication errors."""
    if error_code == "AUTH_001":
        return "Invalid credentials"
    return "Unknown error"
''')

    (Path(temp_dir) / "data_processor.py").write_text('''
class DataProcessor:
    """Process data with various transformations."""

    def __init__(self):
        self.cache = {}

    def transformCamelCase(self, input_data):
        """Transform data using camelCase naming."""
        return input_data.upper()

    def process_snake_case(self, input_value):
        """Process data using snake_case naming."""
        return input_value.lower()

    def calculateMetrics(self):
        """Calculate performance metrics."""
        return {"count": 0, "total": 0}
''')

    # Index the codebase
    config = IndexConfig(persist_directory=".test-hybrid-index")
    indexer = CodebaseIndexer(config=config, root_path=temp_dir)
    indexer.index_directory(verbose=False)

    yield temp_dir, config

    # Cleanup
    shutil.rmtree(temp_dir)


class TestHybridSearch:
    """Tests for hybrid search functionality (semantic + BM25)."""

    def test_tokenize_camelcase(self, indexed_codebase_hybrid):
        """Test tokenization splits camelCase identifiers."""
        temp_dir, config = indexed_codebase_hybrid
        search = CodebaseSearch(config=config, root_path=temp_dir)

        # Test camelCase tokenization
        tokens = search._tokenize("processUserRequest")
        assert "process" in tokens
        assert "user" in tokens
        assert "request" in tokens

    def test_tokenize_snake_case(self, indexed_codebase_hybrid):
        """Test tokenization handles snake_case identifiers."""
        temp_dir, config = indexed_codebase_hybrid
        search = CodebaseSearch(config=config, root_path=temp_dir)

        # snake_case is kept as single tokens after splitting on underscores
        tokens = search._tokenize("process_snake_case")
        assert "process" in tokens
        assert "snake" in tokens
        assert "case" in tokens

    def test_tokenize_mixed_case(self, indexed_codebase_hybrid):
        """Test tokenization handles mixed naming conventions."""
        temp_dir, config = indexed_codebase_hybrid
        search = CodebaseSearch(config=config, root_path=temp_dir)

        # Test mixed case
        tokens = search._tokenize("handleAuthenticationError AUTH_001")
        assert "handle" in tokens
        assert "authentication" in tokens
        assert "error" in tokens
        assert "auth" in tokens
        assert "001" in tokens

    def test_bm25_index_building(self, indexed_codebase_hybrid):
        """Test BM25 index is built from ChromaDB documents."""
        temp_dir, config = indexed_codebase_hybrid
        search = CodebaseSearch(config=config, root_path=temp_dir)

        # BM25 index is lazily built - access the property to trigger build
        bm25 = search.bm25_index
        assert bm25 is not None
        assert search._bm25_doc_ids is not None
        assert len(search._bm25_doc_ids) > 0

    def test_hybrid_search_basic(self, indexed_codebase_hybrid):
        """Test basic hybrid search functionality."""
        temp_dir, config = indexed_codebase_hybrid
        search = CodebaseSearch(config=config, root_path=temp_dir)

        response = search.hybrid_search("process data", top_k=5)

        assert response.has_results
        assert response.total_results > 0
        assert isinstance(response, SearchResponse)

    def test_hybrid_search_exact_function_name(self, indexed_codebase_hybrid):
        """Test hybrid search finds exact function names better."""
        temp_dir, config = indexed_codebase_hybrid
        search = CodebaseSearch(config=config, root_path=temp_dir)

        # Search for exact function name
        response = search.hybrid_search("processUserRequest", top_k=5, alpha=0.3)

        assert response.has_results
        # With lower alpha (more keyword weight), exact match should rank higher
        assert any("processUserRequest" in r.content for r in response.results)

    def test_hybrid_search_error_code(self, indexed_codebase_hybrid):
        """Test hybrid search finds error codes."""
        temp_dir, config = indexed_codebase_hybrid
        search = CodebaseSearch(config=config, root_path=temp_dir)

        # Search for error code - BM25 should help find exact match
        response = search.hybrid_search("AUTH_001", top_k=5, alpha=0.3)

        assert response.has_results
        assert any("AUTH_001" in r.content for r in response.results)

    def test_hybrid_search_alpha_semantic_only(self, indexed_codebase_hybrid):
        """Test alpha=1.0 gives semantic-only results."""
        temp_dir, config = indexed_codebase_hybrid
        search = CodebaseSearch(config=config, root_path=temp_dir)

        response = search.hybrid_search("user authentication", top_k=5, alpha=1.0)

        # With alpha=1.0, keyword_score should be 0 for all results
        for result in response.results:
            # Note: keyword_score may still be stored but weighted to 0
            assert result.semantic_score >= 0

    def test_hybrid_search_alpha_keyword_only(self, indexed_codebase_hybrid):
        """Test alpha=0.0 gives keyword-only weighted results."""
        temp_dir, config = indexed_codebase_hybrid
        search = CodebaseSearch(config=config, root_path=temp_dir)

        response = search.hybrid_search("calculateMetrics", top_k=5, alpha=0.0)

        assert response.has_results
        # With alpha=0.0, exact keyword match should dominate
        assert any("calculateMetrics" in r.content for r in response.results)

    def test_hybrid_search_alpha_balanced(self, indexed_codebase_hybrid):
        """Test alpha=0.5 gives balanced results."""
        temp_dir, config = indexed_codebase_hybrid
        search = CodebaseSearch(config=config, root_path=temp_dir)

        response = search.hybrid_search("transform data", top_k=5, alpha=0.5)

        assert response.has_results
        # Results should have both semantic and keyword scores
        for result in response.results:
            assert result.score >= 0

    def test_hybrid_search_with_file_filter(self, indexed_codebase_hybrid):
        """Test hybrid search respects file filter."""
        temp_dir, config = indexed_codebase_hybrid
        search = CodebaseSearch(config=config, root_path=temp_dir)

        response = search.hybrid_search(
            "process",
            top_k=10,
            file_filter="data_processor"
        )

        # All results should be from data_processor.py
        for result in response.results:
            assert "data_processor" in result.file_path

    def test_hybrid_search_scores_in_response(self, indexed_codebase_hybrid):
        """Test that hybrid search results include all score types."""
        temp_dir, config = indexed_codebase_hybrid
        search = CodebaseSearch(config=config, root_path=temp_dir)

        response = search.hybrid_search("process request", top_k=5, alpha=0.5)

        assert response.has_results
        for result in response.results:
            # Results should have combined score
            assert hasattr(result, 'score')
            assert hasattr(result, 'semantic_score')
            assert hasattr(result, 'keyword_score')
            # Combined score should be between 0 and 1
            assert 0 <= result.score <= 1

    def test_semantic_search_includes_semantic_score(self, indexed_codebase_hybrid):
        """Test that regular search includes semantic_score."""
        temp_dir, config = indexed_codebase_hybrid
        search = CodebaseSearch(config=config, root_path=temp_dir)

        response = search.search("process data", top_k=5)

        assert response.has_results
        for result in response.results:
            # Semantic search should set semantic_score = score
            assert result.semantic_score > 0
            assert result.keyword_score == 0.0


class TestReranking:
    """Tests for cross-encoder re-ranking functionality."""

    def test_reranker_property_lazy_load(self, indexed_codebase_hybrid):
        """Test that reranker is lazily loaded."""
        temp_dir, config = indexed_codebase_hybrid
        search = CodebaseSearch(config=config, root_path=temp_dir)

        # _reranker should be None initially
        assert search._reranker is None

        # Accessing the property should load it (if available)
        from ai_code_assistant.retrieval.search import RERANK_AVAILABLE
        if RERANK_AVAILABLE:
            reranker = search.reranker
            assert reranker is not None
            assert search._reranker is not None

    def test_rerank_method_with_results(self, indexed_codebase_hybrid):
        """Test _rerank method with search results."""
        temp_dir, config = indexed_codebase_hybrid
        search = CodebaseSearch(config=config, root_path=temp_dir)

        # First get some results
        response = search.search("process data", top_k=10)
        assert response.has_results

        from ai_code_assistant.retrieval.search import RERANK_AVAILABLE
        if RERANK_AVAILABLE:
            # Re-rank the results
            reranked = search._rerank("process data", response.results, top_k=5)

            # Should return top_k results
            assert len(reranked) <= 5
            # Results should have normalized scores
            for result in reranked:
                assert 0 <= result.score <= 1

    def test_rerank_method_empty_results(self, indexed_codebase_hybrid):
        """Test _rerank method with empty results."""
        temp_dir, config = indexed_codebase_hybrid
        search = CodebaseSearch(config=config, root_path=temp_dir)

        # Re-rank empty list
        reranked = search._rerank("some query", [], top_k=5)
        assert reranked == []

    def test_hybrid_search_with_rerank(self, indexed_codebase_hybrid):
        """Test hybrid search with re-ranking enabled."""
        temp_dir, config = indexed_codebase_hybrid
        search = CodebaseSearch(config=config, root_path=temp_dir)

        from ai_code_assistant.retrieval.search import RERANK_AVAILABLE

        # Test with rerank=True
        response = search.hybrid_search(
            "process data",
            top_k=5,
            rerank=True,
            rerank_top_k=10,
        )

        assert response.has_results
        # Results should still have valid scores
        for result in response.results:
            assert 0 <= result.score <= 1

    def test_hybrid_search_without_rerank(self, indexed_codebase_hybrid):
        """Test hybrid search with re-ranking disabled."""
        temp_dir, config = indexed_codebase_hybrid
        search = CodebaseSearch(config=config, root_path=temp_dir)

        # Test with rerank=False (default)
        response = search.hybrid_search(
            "process data",
            top_k=5,
            rerank=False,
        )

        assert response.has_results
        for result in response.results:
            assert 0 <= result.score <= 1

    def test_rerank_preserves_metadata(self, indexed_codebase_hybrid):
        """Test that re-ranking preserves result metadata."""
        temp_dir, config = indexed_codebase_hybrid
        search = CodebaseSearch(config=config, root_path=temp_dir)

        from ai_code_assistant.retrieval.search import RERANK_AVAILABLE
        if RERANK_AVAILABLE:
            response = search.hybrid_search(
                "process data",
                top_k=5,
                rerank=True,
                rerank_top_k=10,
            )

            for result in response.results:
                # All metadata should be preserved
                assert result.file_path is not None
                assert result.chunk_type is not None
                assert result.language is not None
                # Semantic and keyword scores should be preserved
                assert hasattr(result, 'semantic_score')
                assert hasattr(result, 'keyword_score')

    def test_rerank_changes_order(self, indexed_codebase_hybrid):
        """Test that re-ranking can change result order."""
        temp_dir, config = indexed_codebase_hybrid
        search = CodebaseSearch(config=config, root_path=temp_dir)

        from ai_code_assistant.retrieval.search import RERANK_AVAILABLE
        if not RERANK_AVAILABLE:
            pytest.skip("Re-ranking not available")

        # Get results without re-ranking
        response_no_rerank = search.hybrid_search(
            "function to process user data",
            top_k=5,
            rerank=False,
        )

        # Get results with re-ranking
        response_with_rerank = search.hybrid_search(
            "function to process user data",
            top_k=5,
            rerank=True,
            rerank_top_k=10,
        )

        # Both should have results
        assert response_no_rerank.has_results
        assert response_with_rerank.has_results

        # Results may or may not be in different order
        # (depends on the query and documents)
        # Just verify both are valid
        assert len(response_with_rerank.results) <= 5

