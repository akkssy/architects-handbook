"""Tests for file editor module."""
import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from ai_code_assistant.config import Config
from ai_code_assistant.llm import LLMManager
from ai_code_assistant.editor.file_editor import FileEditor, EditResult
from ai_code_assistant.editor.diff_handler import DiffHandler, DiffResult, DiffHunk, DiffLine


class TestDiffLine:
    """Tests for DiffLine dataclass."""
    
    def test_str_add(self):
        """Test string representation for add line."""
        line = DiffLine(line_number=1, content="new code", change_type="add")
        assert str(line) == "+ new code"
    
    def test_str_remove(self):
        """Test string representation for remove line."""
        line = DiffLine(line_number=1, content="old code", change_type="remove")
        assert str(line) == "- old code"
    
    def test_str_context(self):
        """Test string representation for context line."""
        line = DiffLine(line_number=1, content="unchanged", change_type="context")
        assert str(line) == "  unchanged"


class TestDiffHunk:
    """Tests for DiffHunk dataclass."""
    
    def test_header(self):
        """Test hunk header generation."""
        hunk = DiffHunk(old_start=10, old_count=5, new_start=10, new_count=7)
        assert hunk.header == "@@ -10,5 +10,7 @@"


class TestDiffResult:
    """Tests for DiffResult dataclass."""
    
    def test_has_changes_true(self):
        """Test has_changes when there are changes."""
        result = DiffResult(
            original_file="test.py",
            modified_file="test.py",
            additions=3,
            deletions=1,
        )
        assert result.has_changes is True
    
    def test_has_changes_false(self):
        """Test has_changes when no changes."""
        result = DiffResult(
            original_file="test.py",
            modified_file="test.py",
            additions=0,
            deletions=0,
        )
        assert result.has_changes is False
    
    def test_summary(self):
        """Test summary generation."""
        result = DiffResult(
            original_file="test.py",
            modified_file="test.py",
            additions=5,
            deletions=2,
        )
        assert result.summary == "+5 -2 lines"


class TestDiffHandler:
    """Tests for DiffHandler class."""
    
    @pytest.fixture
    def handler(self):
        return DiffHandler()
    
    def test_generate_diff_no_changes(self, handler):
        """Test diff generation with identical content."""
        original = "def hello():\n    pass\n"
        result = handler.generate_diff(original, original, "test.py")
        
        assert result.has_changes is False
        assert result.additions == 0
        assert result.deletions == 0
    
    def test_generate_diff_with_additions(self, handler):
        """Test diff generation with additions."""
        original = "def hello():\n    pass\n"
        modified = "def hello():\n    print('hi')\n    pass\n"
        
        result = handler.generate_diff(original, modified, "test.py")
        
        assert result.has_changes is True
        assert result.additions > 0
    
    def test_generate_diff_with_deletions(self, handler):
        """Test diff generation with deletions."""
        original = "def hello():\n    print('hi')\n    pass\n"
        modified = "def hello():\n    pass\n"
        
        result = handler.generate_diff(original, modified, "test.py")
        
        assert result.has_changes is True
        assert result.deletions > 0
    
    def test_format_for_display_no_changes(self, handler):
        """Test formatting when no changes."""
        result = DiffResult(
            original_file="test.py",
            modified_file="test.py",
            additions=0,
            deletions=0,
        )
        formatted = handler.format_for_display(result, use_colors=False)
        assert formatted == "No changes detected."
    
    def test_get_changed_lines(self, handler):
        """Test getting changed line numbers."""
        original = "line1\nline2\nline3\n"
        modified = "line1\nnew_line\nline3\n"
        
        diff_result = handler.generate_diff(original, modified, "test.py")
        added, removed = handler.get_changed_lines(diff_result)
        
        assert len(added) > 0 or len(removed) > 0


class TestEditResult:
    """Tests for EditResult dataclass."""
    
    def test_success_true(self):
        """Test success when no error and has content."""
        result = EditResult(
            filename="test.py",
            original_content="old",
            modified_content="new",
            instruction="change",
            mode="edit",
        )
        assert result.success is True
    
    def test_success_false_with_error(self):
        """Test success when error present."""
        result = EditResult(
            filename="test.py",
            original_content="old",
            modified_content="new",
            instruction="change",
            mode="edit",
            error="Something went wrong",
        )
        assert result.success is False
    
    def test_has_changes(self):
        """Test has_changes property."""
        result = EditResult(
            filename="test.py",
            original_content="old",
            modified_content="new",
            instruction="change",
            mode="edit",
        )
        assert result.has_changes is True

    def test_to_dict(self):
        """Test to_dict method."""
        result = EditResult(
            filename="test.py",
            original_content="old",
            modified_content="new",
            instruction="change",
            mode="edit",
            applied=True,
        )
        d = result.to_dict()

        assert d["filename"] == "test.py"
        assert d["instruction"] == "change"
        assert d["mode"] == "edit"
        assert d["success"] is True
        assert d["applied"] is True


class TestFileEditor:
    """Tests for FileEditor class."""

    @pytest.fixture
    def config(self):
        return Config()

    @pytest.fixture
    def mock_llm(self):
        return MagicMock(spec=LLMManager)

    @pytest.fixture
    def editor(self, config, mock_llm):
        return FileEditor(config, mock_llm)

    def test_edit_file_not_found(self, editor):
        """Test editing non-existent file."""
        result = editor.edit_file(
            file_path=Path("/nonexistent/file.py"),
            instruction="Add docstring",
        )

        assert result.success is False
        assert "not found" in result.error.lower()

    def test_edit_file_success(self, editor, mock_llm):
        """Test successful file edit."""
        mock_llm.invoke_with_template.return_value = '''
```python
def hello():
    """Say hello."""
    print("Hello, World!")
```
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write('def hello():\n    print("Hello, World!")\n')
            temp_path = Path(f.name)

        try:
            result = editor.edit_file(
                file_path=temp_path,
                instruction="Add docstring",
                preview=True,
            )

            assert result.success is True
            assert result.has_changes is True
            assert '"""Say hello."""' in result.modified_content
        finally:
            temp_path.unlink(missing_ok=True)

    def test_edit_file_with_backup(self, editor, mock_llm):
        """Test file edit creates backup."""
        mock_llm.invoke_with_template.return_value = '''
```python
def hello():
    """Updated."""
    pass
```
'''
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = Path(tmpdir) / "test.py"
            temp_path.write_text('def hello():\n    pass\n')

            result = editor.edit_file(
                file_path=temp_path,
                instruction="Add docstring",
                create_backup=True,
            )

            assert result.success is True
            assert result.backup_path is not None
            assert Path(result.backup_path).exists()

    def test_edit_code_directly(self, editor, mock_llm):
        """Test editing code string directly."""
        mock_llm.invoke_with_template.return_value = '''
```python
def add(a: int, b: int) -> int:
    return a + b
```
'''
        result = editor.edit_code(
            code="def add(a, b): return a + b",
            instruction="Add type hints",
            language="python",
        )

        assert result.success is True
        assert "int" in result.modified_content

    def test_extract_code_with_language(self, editor):
        """Test code extraction with language tag."""
        response = "Here's the code:\n```python\ndef test():\n    pass\n```"
        code = editor._extract_code(response, "python")
        assert code == "def test():\n    pass"

    def test_extract_code_generic(self, editor):
        """Test code extraction with generic block."""
        response = "```\ndef test():\n    pass\n```"
        code = editor._extract_code(response, "python")
        assert "def test" in code

    def test_restore_backup(self, editor):
        """Test backup restoration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original = Path(tmpdir) / "original.py"
            backup = Path(tmpdir) / "backup.py"

            original.write_text("modified content")
            backup.write_text("original content")

            success = editor.restore_backup(backup, original)

            assert success is True
            assert original.read_text() == "original content"

