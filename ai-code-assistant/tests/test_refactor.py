"""Tests for the multi-file refactoring module."""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from ai_code_assistant.config import Config
from ai_code_assistant.refactor.change_plan import (
    ChangePlan,
    FileChange,
    ChangeType,
    RefactorResult,
)
from ai_code_assistant.refactor.analyzer import RefactorAnalyzer
from ai_code_assistant.refactor.multi_file_editor import MultiFileEditor


# ============== FileChange Tests ==============

class TestFileChange:
    """Tests for FileChange dataclass."""
    
    def test_success_without_error(self):
        change = FileChange(
            file_path="test.py",
            change_type=ChangeType.MODIFY,
            description="Test change",
        )
        assert change.success is True
    
    def test_success_with_error(self):
        change = FileChange(
            file_path="test.py",
            change_type=ChangeType.MODIFY,
            description="Test change",
            error="Something went wrong",
        )
        assert change.success is False
    
    def test_has_changes_modify(self):
        change = FileChange(
            file_path="test.py",
            change_type=ChangeType.MODIFY,
            description="Test change",
            original_content="old",
            new_content="new",
        )
        assert change.has_changes is True
    
    def test_has_changes_no_diff(self):
        change = FileChange(
            file_path="test.py",
            change_type=ChangeType.MODIFY,
            description="Test change",
            original_content="same",
            new_content="same",
        )
        assert change.has_changes is False
    
    def test_has_changes_delete(self):
        change = FileChange(
            file_path="test.py",
            change_type=ChangeType.DELETE,
            description="Delete file",
        )
        assert change.has_changes is True
    
    def test_has_changes_create(self):
        change = FileChange(
            file_path="test.py",
            change_type=ChangeType.CREATE,
            description="Create file",
            new_content="content",
        )
        assert change.has_changes is True
    
    def test_to_dict(self):
        change = FileChange(
            file_path="test.py",
            change_type=ChangeType.MODIFY,
            description="Test change",
            priority="high",
        )
        result = change.to_dict()
        assert result["file_path"] == "test.py"
        assert result["change_type"] == "modify"
        assert result["priority"] == "high"


# ============== ChangePlan Tests ==============

class TestChangePlan:
    """Tests for ChangePlan dataclass."""
    
    def test_total_files(self):
        plan = ChangePlan(
            instruction="Test",
            summary="Test plan",
            changes=[
                FileChange("a.py", ChangeType.MODIFY, "Change A"),
                FileChange("b.py", ChangeType.CREATE, "Create B"),
            ],
        )
        assert plan.total_files == 2
    
    def test_files_by_type(self):
        plan = ChangePlan(
            instruction="Test",
            summary="Test plan",
            changes=[
                FileChange("a.py", ChangeType.MODIFY, "Modify"),
                FileChange("b.py", ChangeType.CREATE, "Create"),
                FileChange("c.py", ChangeType.DELETE, "Delete"),
                FileChange("d.py", ChangeType.RENAME, "Rename"),
            ],
        )
        assert len(plan.files_to_modify) == 1
        assert len(plan.files_to_create) == 1
        assert len(plan.files_to_delete) == 1
        assert len(plan.files_to_rename) == 1
    
    def test_get_ordered_changes_by_priority(self):
        plan = ChangePlan(
            instruction="Test",
            summary="Test plan",
            changes=[
                FileChange("low.py", ChangeType.MODIFY, "Low", priority="low"),
                FileChange("high.py", ChangeType.MODIFY, "High", priority="high"),
                FileChange("med.py", ChangeType.MODIFY, "Med", priority="medium"),
            ],
        )
        ordered = plan.get_ordered_changes()
        assert ordered[0].file_path == "high.py"
        assert ordered[1].file_path == "med.py"
        assert ordered[2].file_path == "low.py"
    
    def test_get_ordered_changes_with_dependencies(self):
        plan = ChangePlan(
            instruction="Test",
            summary="Test plan",
            changes=[
                FileChange("b.py", ChangeType.MODIFY, "B", depends_on=["a.py"]),
                FileChange("a.py", ChangeType.MODIFY, "A"),
            ],
        )
        ordered = plan.get_ordered_changes()
        # a.py should come before b.py due to dependency
        assert ordered[0].file_path == "a.py"
        assert ordered[1].file_path == "b.py"
    
    def test_to_dict(self):
        plan = ChangePlan(
            instruction="Test instruction",
            summary="Test summary",
            complexity="high",
            risks=["Risk 1"],
        )
        result = plan.to_dict()
        assert result["instruction"] == "Test instruction"
        assert result["summary"] == "Test summary"
        assert result["complexity"] == "high"
        assert "Risk 1" in result["risks"]


# ============== RefactorResult Tests ==============

class TestRefactorResult:
    """Tests for RefactorResult dataclass."""

    def test_success_without_error(self):
        plan = ChangePlan("Test", "Summary")
        result = RefactorResult(plan=plan)
        assert result.success is True

    def test_success_with_error(self):
        plan = ChangePlan("Test", "Summary")
        result = RefactorResult(plan=plan, error="Failed")
        assert result.success is False

    def test_files_changed(self):
        plan = ChangePlan(
            instruction="Test",
            summary="Summary",
            changes=[
                FileChange("a.py", ChangeType.MODIFY, "A", applied=True),
                FileChange("b.py", ChangeType.MODIFY, "B", applied=False),
                FileChange("c.py", ChangeType.MODIFY, "C", applied=True),
            ],
        )
        result = RefactorResult(plan=plan, applied=True)
        assert result.files_changed == 2

    def test_files_failed(self):
        plan = ChangePlan(
            instruction="Test",
            summary="Summary",
            changes=[
                FileChange("a.py", ChangeType.MODIFY, "A", error="Failed"),
                FileChange("b.py", ChangeType.MODIFY, "B"),
            ],
        )
        result = RefactorResult(plan=plan)
        assert result.files_failed == 1

    def test_to_dict(self):
        plan = ChangePlan("Test", "Summary")
        result = RefactorResult(plan=plan, applied=True, backup_dir="/backup")
        data = result.to_dict()
        assert data["success"] is True
        assert data["applied"] is True
        assert data["backup_dir"] == "/backup"


# ============== RefactorAnalyzer Tests ==============

class TestRefactorAnalyzer:
    """Tests for RefactorAnalyzer."""

    @pytest.fixture
    def mock_config(self):
        config = Mock(spec=Config)
        config.refactor = Mock()
        config.refactor.max_file_size_kb = 500
        config.languages = {}
        return config

    @pytest.fixture
    def mock_llm(self):
        return Mock()

    def test_analyze_no_files(self, mock_config, mock_llm):
        analyzer = RefactorAnalyzer(mock_config, mock_llm)
        plan = analyzer.analyze("Add type hints", [])
        assert plan.summary == "No files to analyze"
        assert len(plan.changes) == 0

    def test_parse_analysis_valid_json(self, mock_config, mock_llm):
        analyzer = RefactorAnalyzer(mock_config, mock_llm)

        response = '''```json
        {
            "summary": "Add type hints to functions",
            "affected_files": [
                {
                    "file_path": "main.py",
                    "change_type": "modify",
                    "description": "Add type hints",
                    "priority": "high"
                }
            ],
            "risks": ["May break compatibility"],
            "estimated_complexity": "medium"
        }
        ```'''

        plan = analyzer._parse_analysis("Add type hints", response)
        assert plan.summary == "Add type hints to functions"
        assert len(plan.changes) == 1
        assert plan.changes[0].file_path == "main.py"
        assert plan.changes[0].change_type == ChangeType.MODIFY
        assert plan.complexity == "medium"

    def test_parse_analysis_invalid_json(self, mock_config, mock_llm):
        analyzer = RefactorAnalyzer(mock_config, mock_llm)
        plan = analyzer._parse_analysis("Test", "not valid json")
        assert "Could not parse" in plan.summary

    def test_extract_json_from_code_block(self, mock_config, mock_llm):
        analyzer = RefactorAnalyzer(mock_config, mock_llm)
        text = '```json\n{"key": "value"}\n```'
        result = analyzer._extract_json(text)
        assert result == {"key": "value"}

    def test_extract_json_raw(self, mock_config, mock_llm):
        analyzer = RefactorAnalyzer(mock_config, mock_llm)
        text = 'Some text {"key": "value"} more text'
        result = analyzer._extract_json(text)
        assert result == {"key": "value"}


# ============== MultiFileEditor Tests ==============

class TestMultiFileEditor:
    """Tests for MultiFileEditor."""

    @pytest.fixture
    def mock_config(self):
        config = Mock(spec=Config)
        config.refactor = Mock()
        config.refactor.max_file_size_kb = 500
        config.refactor.max_files = 20
        config.languages = {}
        return config

    @pytest.fixture
    def mock_llm(self):
        return Mock()

    def test_format_file_contents(self, mock_config, mock_llm):
        editor = MultiFileEditor(mock_config, mock_llm)
        contents = {
            "test.py": "print('hello')",
            "main.js": "console.log('hi')",
        }
        result = editor._format_file_contents(contents)
        assert "### test.py" in result
        assert "print('hello')" in result
        assert "### main.js" in result

    def test_parse_multi_file_response(self, mock_config, mock_llm):
        editor = MultiFileEditor(mock_config, mock_llm)

        plan = ChangePlan(
            instruction="Test",
            summary="Test",
            changes=[
                FileChange("test.py", ChangeType.MODIFY, "Modify"),
            ],
        )

        response = '''### FILE: test.py
```python
def hello():
    print("world")
```'''

        editor._parse_multi_file_response(plan, response)
        assert plan.changes[0].new_content == 'def hello():\n    print("world")'

    def test_read_files_nonexistent(self, mock_config, mock_llm):
        editor = MultiFileEditor(mock_config, mock_llm)
        result = editor._read_files([Path("/nonexistent/file.py")])
        assert result == {}

    def test_read_files_existing(self, mock_config, mock_llm, tmp_path):
        editor = MultiFileEditor(mock_config, mock_llm)

        # Create a test file
        test_file = tmp_path / "test.py"
        test_file.write_text("print('hello')")

        result = editor._read_files([test_file])
        assert str(test_file) in result
        assert result[str(test_file)] == "print('hello')"

