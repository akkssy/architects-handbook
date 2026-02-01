"""Tests for code analyzer module."""
import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from ai_code_assistant.config import Config
from ai_code_assistant.llm import LLMManager
from ai_code_assistant.reviewer.analyzer import (
    CodeAnalyzer, ReviewResult, ReviewIssue
)


class TestReviewIssue:
    """Tests for ReviewIssue dataclass."""
    
    def test_create_issue(self):
        """Test creating a review issue."""
        issue = ReviewIssue(
            line_start=10,
            line_end=15,
            category="bugs",
            severity="warning",
            title="Test Issue",
            description="Test description",
            suggestion="Test fix",
            confidence=0.8,
        )
        
        assert issue.line_start == 10
        assert issue.line_end == 15
        assert issue.category == "bugs"
        assert issue.severity == "warning"
        assert issue.confidence == 0.8


class TestReviewResult:
    """Tests for ReviewResult dataclass."""
    
    def test_empty_result(self):
        """Test creating an empty review result."""
        result = ReviewResult(
            filename="test.py",
            language="python",
            summary="No issues found",
        )
        
        assert result.filename == "test.py"
        assert result.language == "python"
        assert len(result.issues) == 0
        assert result.error is None
    
    def test_critical_issues_property(self):
        """Test filtering critical issues."""
        issues = [
            ReviewIssue(1, 1, "bugs", "critical", "Critical", "", "", 0.9),
            ReviewIssue(2, 2, "style", "warning", "Warning", "", "", 0.8),
            ReviewIssue(3, 3, "security", "critical", "Critical2", "", "", 0.9),
        ]
        result = ReviewResult(
            filename="test.py",
            language="python",
            summary="Test",
            issues=issues,
        )
        
        assert len(result.critical_issues) == 2
        assert all(i.severity == "critical" for i in result.critical_issues)
    
    def test_warnings_property(self):
        """Test filtering warning issues."""
        issues = [
            ReviewIssue(1, 1, "bugs", "warning", "Warn1", "", "", 0.8),
            ReviewIssue(2, 2, "style", "critical", "Critical", "", "", 0.9),
            ReviewIssue(3, 3, "perf", "warning", "Warn2", "", "", 0.7),
        ]
        result = ReviewResult(
            filename="test.py",
            language="python",
            summary="Test",
            issues=issues,
        )
        
        assert len(result.warnings) == 2
    
    def test_suggestions_property(self):
        """Test filtering suggestion issues."""
        issues = [
            ReviewIssue(1, 1, "style", "suggestion", "Sug1", "", "", 0.6),
            ReviewIssue(2, 2, "style", "warning", "Warning", "", "", 0.8),
        ]
        result = ReviewResult(
            filename="test.py",
            language="python",
            summary="Test",
            issues=issues,
        )
        
        assert len(result.suggestions) == 1


class TestCodeAnalyzer:
    """Tests for CodeAnalyzer class."""
    
    @pytest.fixture
    def config(self):
        return Config()
    
    @pytest.fixture
    def mock_llm(self):
        return MagicMock(spec=LLMManager)
    
    @pytest.fixture
    def analyzer(self, config, mock_llm):
        return CodeAnalyzer(config, mock_llm)
    
    def test_review_nonexistent_file(self, analyzer):
        """Test reviewing a non-existent file."""
        result = analyzer.review_file(Path("/nonexistent/file.py"))
        
        assert result.error is not None
        assert "not found" in result.error.lower()
    
    def test_review_file_too_large(self, analyzer, config):
        """Test reviewing a file that's too large."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            # Write content larger than max (default 500KB)
            f.write("x" * (600 * 1024))
            f.flush()
            
            result = analyzer.review_file(Path(f.name))
            assert result.error is not None
            assert "too large" in result.error.lower()
    
    def test_review_code_success(self, analyzer, mock_llm):
        """Test successful code review."""
        mock_llm.invoke_with_template.return_value = '''
        {"summary": "Good code", "issues": [], "overall_quality": "good"}
        '''
        
        result = analyzer.review_code("print('hello')", "python")
        
        assert result.error is None
        assert result.summary == "Good code"
    
    def test_parse_json_from_code_block(self, analyzer, mock_llm):
        """Test parsing JSON from code block response."""
        mock_llm.invoke_with_template.return_value = '''
        Here is my review:
        ```json
        {"summary": "Test", "issues": [], "overall_quality": "good"}
        ```
        '''
        
        result = analyzer.review_code("x = 1", "python")
        assert result.summary == "Test"
    
    def test_extract_json_direct(self, analyzer):
        """Test extracting JSON directly."""
        response = '{"summary": "test"}'
        extracted = analyzer._extract_json(response)
        assert '{"summary": "test"}' in extracted
    
    def test_repair_json_trailing_comma(self, analyzer):
        """Test repairing JSON with trailing comma."""
        broken = '{"items": [1, 2, 3,]}'
        repaired = analyzer._repair_json(broken)
        assert ',]' not in repaired

