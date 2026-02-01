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

