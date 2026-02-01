"""Tests for configuration module."""
import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch

from ai_code_assistant.config import (
    Config, LLMConfig, ReviewConfig, GenerationConfig,
    OutputConfig, load_config, find_config_file, get_language_by_extension
)


class TestLLMConfig:
    """Tests for LLMConfig model."""

    def test_default_values(self):
        """Test default configuration values."""
        config = LLMConfig()
        assert config.model == "deepseek-coder:6.7b"
        assert config.base_url == "http://localhost:11434"
        assert config.temperature == 0.1
        assert config.max_tokens == 4096
        assert config.timeout == 120

    def test_custom_values(self):
        """Test custom configuration values."""
        config = LLMConfig(
            model="custom-model",
            temperature=0.5,
            max_tokens=2048
        )
        assert config.model == "custom-model"
        assert config.temperature == 0.5
        assert config.max_tokens == 2048


class TestReviewConfig:
    """Tests for ReviewConfig model."""

    def test_default_values(self):
        """Test default review configuration."""
        config = ReviewConfig()
        assert "critical" in config.severity_levels
        assert "warning" in config.severity_levels
        assert "bugs" in config.categories
        assert config.max_file_size_kb == 500
        assert config.include_line_numbers is True


class TestGenerationConfig:
    """Tests for GenerationConfig model."""

    def test_default_values(self):
        """Test default generation configuration."""
        config = GenerationConfig()
        assert config.include_type_hints is True
        assert config.include_docstrings is True
        assert config.default_mode == "function"


class TestConfig:
    """Tests for main Config class."""

    def test_default_config(self):
        """Test default configuration."""
        config = Config()
        assert config.llm is not None
        assert isinstance(config.llm, LLMConfig)
        assert config.review is not None
        assert config.generation is not None
        assert config.output is not None

    def test_nested_config_access(self):
        """Test accessing nested configuration."""
        config = Config()
        assert config.llm.model == "deepseek-coder:6.7b"
        assert config.output.default_format == "console"


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_default_config(self):
        """Test loading default config when no file exists."""
        config = load_config(Path("/nonexistent/config.yaml"))
        assert config is not None
        assert isinstance(config, Config)

    def test_load_from_yaml(self):
        """Test loading configuration from YAML file."""
        yaml_content = """
llm:
  model: "test-model"
  temperature: 0.5
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()

            try:
                config = load_config(Path(f.name))
                assert config.llm.model == "test-model"
                assert config.llm.temperature == 0.5
            finally:
                os.unlink(f.name)


class TestGetLanguageByExtension:
    """Tests for language detection from file extension."""

    def test_python_detection(self):
        """Test Python file detection."""
        config = Config()
        lang = get_language_by_extension(config, Path("test.py"))
        assert lang == "python"

    def test_javascript_detection(self):
        """Test JavaScript file detection."""
        config = Config()
        lang = get_language_by_extension(config, Path("test.js"))
        assert lang == "javascript"

    def test_typescript_detection(self):
        """Test TypeScript file detection."""
        config = Config()
        lang = get_language_by_extension(config, Path("test.ts"))
        assert lang == "typescript"

    def test_unknown_extension(self):
        """Test unknown file extension."""
        config = Config()
        lang = get_language_by_extension(config, Path("test.unknown"))
        assert lang is None

