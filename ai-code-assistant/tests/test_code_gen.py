"""Tests for code generator module."""
import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from ai_code_assistant.config import Config
from ai_code_assistant.llm import LLMManager
from ai_code_assistant.generator.code_gen import CodeGenerator, GenerationResult


class TestGenerationResult:
    """Tests for GenerationResult dataclass."""
    
    def test_success_with_code(self):
        """Test success property when code is present."""
        result = GenerationResult(
            code="def hello(): pass",
            language="python",
            mode="function",
            description="Test",
        )
        assert result.success is True
    
    def test_success_with_empty_code(self):
        """Test success property when code is empty."""
        result = GenerationResult(
            code="",
            language="python",
            mode="function",
            description="Test",
        )
        assert result.success is False
    
    def test_success_with_error(self):
        """Test success property when error is present."""
        result = GenerationResult(
            code="def hello(): pass",
            language="python",
            mode="function",
            description="Test",
            error="Generation failed",
        )
        assert result.success is False
    
    def test_success_with_whitespace_only_code(self):
        """Test success property with whitespace-only code."""
        result = GenerationResult(
            code="   \n  \t  ",
            language="python",
            mode="function",
            description="Test",
        )
        assert result.success is False


class TestCodeGenerator:
    """Tests for CodeGenerator class."""
    
    @pytest.fixture
    def config(self):
        return Config()
    
    @pytest.fixture
    def mock_llm(self):
        return MagicMock(spec=LLMManager)
    
    @pytest.fixture
    def generator(self, config, mock_llm):
        return CodeGenerator(config, mock_llm)
    
    def test_generate_function_success(self, generator, mock_llm):
        """Test successful function generation."""
        mock_llm.invoke_with_template.return_value = '''
```python
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b
```
'''
        result = generator.generate_function(
            description="Add two numbers",
            name="add",
            language="python",
        )
        
        assert result.success is True
        assert "def add" in result.code
        assert result.mode == "function"
    
    def test_generate_function_error(self, generator, mock_llm):
        """Test function generation with error."""
        mock_llm.invoke_with_template.side_effect = Exception("LLM error")
        
        result = generator.generate_function(
            description="Test",
            name="test",
        )
        
        assert result.success is False
        assert "LLM error" in result.error
    
    def test_generate_class_success(self, generator, mock_llm):
        """Test successful class generation."""
        mock_llm.invoke_with_template.return_value = '''
```python
class Calculator:
    """A simple calculator."""
    def add(self, a, b):
        return a + b
```
'''
        result = generator.generate_class(
            description="A calculator class",
            name="Calculator",
        )
        
        assert result.success is True
        assert "class Calculator" in result.code
        assert result.mode == "class"
    
    def test_generate_script_success(self, generator, mock_llm):
        """Test successful script generation."""
        mock_llm.invoke_with_template.return_value = '''
```python
#!/usr/bin/env python3
import sys
print("Hello")
```
'''
        result = generator.generate_script(
            description="Print hello",
            requirements=["Print greeting"],
        )
        
        assert result.success is True
        assert result.mode == "script"
    
    def test_generate_tests_success(self, generator, mock_llm):
        """Test successful test generation."""
        mock_llm.invoke_with_template.return_value = '''
```python
import pytest
def test_add():
    assert add(1, 2) == 3
```
'''
        result = generator.generate_tests(
            source_code="def add(a, b): return a + b",
        )
        
        assert result.success is True
        assert result.mode == "test"
        assert "pytest" in result.code
    
    def test_extract_code_language_specific(self, generator):
        """Test extracting code with language-specific block."""
        response = "Here is the code:\n```python\ndef hello():\n    pass\n```\nDone."
        code = generator._extract_code(response, "python")
        assert code == "def hello():\n    pass"
    
    def test_extract_code_generic_block(self, generator):
        """Test extracting code with generic code block."""
        response = "```\ndef hello():\n    pass\n```"
        code = generator._extract_code(response, "python")
        assert "def hello" in code
    
    def test_extract_code_no_block(self, generator):
        """Test extracting code when no block markers."""
        response = "def hello():\n    print('hi')"
        code = generator._extract_code(response, "python")
        assert "def hello" in code
    
    def test_save_to_file(self, generator):
        """Test saving generated code to file."""
        result = GenerationResult(
            code="print('hello')",
            language="python",
            mode="script",
            description="Test",
        )
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "output.py"
            success = generator.save_to_file(result, output)
            
            assert success is True
            assert output.exists()
            assert output.read_text() == "print('hello')"

