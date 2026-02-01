"""Tests for output formatters."""
import pytest
import json
import tempfile
from pathlib import Path

from ai_code_assistant.reviewer.analyzer import ReviewResult, ReviewIssue
from ai_code_assistant.generator.code_gen import GenerationResult
from ai_code_assistant.utils.formatters import (
    ConsoleFormatter, MarkdownFormatter, JsonFormatter, get_formatter
)


class TestReviewResultFixtures:
    """Fixtures for testing formatters."""
    
    @pytest.fixture
    def sample_issue(self):
        """Create a sample review issue."""
        return ReviewIssue(
            line_start=10,
            line_end=12,
            category="bugs",
            severity="warning",
            title="Unused variable",
            description="Variable 'x' is assigned but never used",
            suggestion="Remove the unused variable or use it",
            confidence=0.85,
        )
    
    @pytest.fixture
    def sample_review_result(self, sample_issue):
        """Create a sample review result."""
        return ReviewResult(
            filename="test.py",
            language="python",
            summary="Code has some issues that need attention",
            overall_quality="Good",
            issues=[sample_issue],
            metrics={"lines": 100, "functions": 5},
        )
    
    @pytest.fixture
    def sample_generation_result(self):
        """Create a sample generation result."""
        return GenerationResult(
            code="def hello():\n    print('Hello, World!')",
            language="python",
            mode="function",
            description="A simple hello function",
        )


class TestConsoleFormatter(TestReviewResultFixtures):
    """Tests for ConsoleFormatter."""
    
    def test_format_review_with_error(self):
        """Test formatting review with error."""
        result = ReviewResult(
            filename="test.py",
            language="python",
            summary="",
            error="Failed to parse file",
        )
        formatter = ConsoleFormatter(use_colors=False)
        output = formatter.format_review(result)
        assert "Failed to parse file" in output

    def test_format_generation_with_error(self):
        """Test formatting generation with error."""
        result = GenerationResult(
            code="",
            language="python",
            mode="function",
            description="",
            error="Failed to generate",
        )
        formatter = ConsoleFormatter(use_colors=False)
        output = formatter.format_generation(result)
        assert "Failed to generate" in output


class TestMarkdownFormatter(TestReviewResultFixtures):
    """Tests for MarkdownFormatter."""
    
    def test_format_review(self, sample_review_result):
        """Test formatting review as markdown."""
        formatter = MarkdownFormatter()
        output = formatter.format_review(sample_review_result)
        
        assert "# Code Review: test.py" in output
        assert "**Language:** python" in output
        assert "Unused variable" in output
    
    def test_format_review_with_error(self):
        """Test formatting review with error."""
        result = ReviewResult(
            filename="test.py",
            language="python",
            summary="",
            error="Parse error",
        )
        formatter = MarkdownFormatter()
        output = formatter.format_review(result)

        assert "**Error:** Parse error" in output
    
    def test_format_generation(self, sample_generation_result):
        """Test formatting generation as markdown."""
        formatter = MarkdownFormatter()
        output = formatter.format_generation(sample_generation_result)
        
        assert "# Generated Code" in output
        assert "**Mode:** function" in output
        assert "def hello():" in output


class TestJsonFormatter(TestReviewResultFixtures):
    """Tests for JsonFormatter."""
    
    def test_format_review(self, sample_review_result):
        """Test formatting review as JSON."""
        formatter = JsonFormatter()
        output = formatter.format_review(sample_review_result)
        
        data = json.loads(output)
        assert data["filename"] == "test.py"
        assert data["language"] == "python"
        assert len(data["issues"]) == 1
        assert data["issues"][0]["title"] == "Unused variable"
    
    def test_format_generation(self, sample_generation_result):
        """Test formatting generation as JSON."""
        formatter = JsonFormatter()
        output = formatter.format_generation(sample_generation_result)

        data = json.loads(output)
        assert data["mode"] == "function"
        assert data["language"] == "python"
        assert "def hello():" in data["code"]


class TestGetFormatter:
    """Tests for get_formatter function."""
    
    def test_get_console_formatter(self):
        """Test getting console formatter."""
        formatter = get_formatter("console")
        assert isinstance(formatter, ConsoleFormatter)
    
    def test_get_markdown_formatter(self):
        """Test getting markdown formatter."""
        formatter = get_formatter("markdown")
        assert isinstance(formatter, MarkdownFormatter)
    
    def test_get_json_formatter(self):
        """Test getting JSON formatter."""
        formatter = get_formatter("json")
        assert isinstance(formatter, JsonFormatter)
    
    def test_get_unknown_formatter_defaults_to_console(self):
        """Test unknown format defaults to console."""
        formatter = get_formatter("unknown")
        assert isinstance(formatter, ConsoleFormatter)
    
    def test_case_insensitive(self):
        """Test format type is case insensitive."""
        formatter = get_formatter("MARKDOWN")
        assert isinstance(formatter, MarkdownFormatter)


class TestBaseFormatterSave(TestReviewResultFixtures):
    """Tests for BaseFormatter.save method."""
    
    def test_save_to_file(self, sample_review_result):
        """Test saving formatted content to file."""
        formatter = MarkdownFormatter()
        content = formatter.format_review(sample_review_result)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "review.md"
            formatter.save(content, output_path)
            
            assert output_path.exists()
            saved_content = output_path.read_text()
            assert "# Code Review: test.py" in saved_content

