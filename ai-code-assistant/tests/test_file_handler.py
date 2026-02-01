"""Tests for file handler utilities."""
import pytest
import tempfile
import os
from pathlib import Path

from ai_code_assistant.config import Config
from ai_code_assistant.utils.file_handler import FileHandler


class TestFileHandler:
    """Tests for FileHandler class."""
    
    @pytest.fixture
    def handler(self):
        """Create a FileHandler instance for testing."""
        config = Config()
        return FileHandler(config)
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    def test_default_ignore_patterns(self, handler):
        """Test that default ignore patterns are set."""
        assert "__pycache__" in handler.ignore_patterns
        assert ".git" in handler.ignore_patterns
        assert "node_modules" in handler.ignore_patterns
    
    def test_add_ignore_pattern(self, handler):
        """Test adding custom ignore pattern."""
        handler.add_ignore_pattern("*.custom")
        assert "*.custom" in handler.ignore_patterns
    
    def test_is_supported_file_python(self, handler):
        """Test Python file is supported."""
        assert handler.is_supported_file(Path("test.py")) is True
    
    def test_is_supported_file_javascript(self, handler):
        """Test JavaScript file is supported."""
        assert handler.is_supported_file(Path("test.js")) is True
    
    def test_is_supported_file_unknown(self, handler):
        """Test unknown file is not supported."""
        assert handler.is_supported_file(Path("test.xyz")) is False
    
    def test_should_ignore_pycache(self, handler):
        """Test __pycache__ is ignored."""
        assert handler.should_ignore(Path("__pycache__")) is True
    
    def test_should_ignore_git(self, handler):
        """Test .git is ignored."""
        assert handler.should_ignore(Path(".git")) is True
    
    def test_should_not_ignore_normal_file(self, handler):
        """Test normal file is not ignored."""
        assert handler.should_ignore(Path("main.py")) is False
    
    def test_read_file_success(self, handler, temp_dir):
        """Test reading a file successfully."""
        test_file = temp_dir / "test.py"
        test_file.write_text("print('hello')")
        
        content, error = handler.read_file(test_file)
        assert content == "print('hello')"
        assert error is None
    
    def test_read_file_not_found(self, handler):
        """Test reading non-existent file."""
        content, error = handler.read_file(Path("/nonexistent/file.py"))
        assert content == ""
        assert error is not None
        assert "not found" in error.lower()
    
    def test_read_file_directory(self, handler, temp_dir):
        """Test reading a directory returns error."""
        content, error = handler.read_file(temp_dir)
        assert content == ""
        assert error is not None
        assert "not a file" in error.lower()
    
    def test_write_file_success(self, handler, temp_dir):
        """Test writing a file successfully."""
        test_file = temp_dir / "output.py"
        error = handler.write_file(test_file, "print('test')")
        
        assert error is None
        assert test_file.exists()
        assert test_file.read_text() == "print('test')"
    
    def test_write_file_create_dirs(self, handler, temp_dir):
        """Test writing file with directory creation."""
        test_file = temp_dir / "subdir" / "nested" / "output.py"
        error = handler.write_file(test_file, "content", create_dirs=True)
        
        assert error is None
        assert test_file.exists()
    
    def test_write_file_with_backup(self, handler, temp_dir):
        """Test writing file with backup."""
        test_file = temp_dir / "test.py"
        test_file.write_text("original content")
        
        error = handler.write_file(test_file, "new content", backup=True)
        
        assert error is None
        assert test_file.read_text() == "new content"
        
        backup_file = test_file.with_suffix(".py.bak")
        assert backup_file.exists()
        assert backup_file.read_text() == "original content"
    
    def test_find_code_files(self, handler, temp_dir):
        """Test finding code files in directory."""
        # Create test files
        (temp_dir / "main.py").write_text("# main")
        (temp_dir / "util.js").write_text("// util")
        (temp_dir / "readme.txt").write_text("readme")
        
        files = list(handler.find_code_files(temp_dir))
        
        assert len(files) == 2
        names = [f.name for f in files]
        assert "main.py" in names
        assert "util.js" in names
        assert "readme.txt" not in names
    
    def test_find_code_files_recursive(self, handler, temp_dir):
        """Test finding code files recursively."""
        (temp_dir / "main.py").write_text("# main")
        subdir = temp_dir / "subdir"
        subdir.mkdir()
        (subdir / "nested.py").write_text("# nested")
        
        files = list(handler.find_code_files(temp_dir, recursive=True))
        
        assert len(files) == 2
    
    def test_get_file_info(self, handler, temp_dir):
        """Test getting file information."""
        test_file = temp_dir / "test.py"
        test_file.write_text("print('hello')")
        
        info = handler.get_file_info(test_file)
        
        assert info["exists"] is True
        assert info["language"] == "python"
        assert info["extension"] == ".py"
        assert info["name"] == "test.py"
    
    def test_get_file_info_not_found(self, handler):
        """Test getting info for non-existent file."""
        info = handler.get_file_info(Path("/nonexistent/file.py"))
        assert info["exists"] is False
    
    def test_batch_read(self, handler, temp_dir):
        """Test batch reading files."""
        file1 = temp_dir / "file1.py"
        file2 = temp_dir / "file2.py"
        file1.write_text("content1")
        file2.write_text("content2")
        
        results = handler.batch_read([file1, file2])
        
        assert len(results) == 2
        assert results[file1][0] == "content1"
        assert results[file2][0] == "content2"

