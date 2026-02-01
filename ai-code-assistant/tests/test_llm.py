"""Tests for LLM manager module."""
import pytest
from unittest.mock import Mock, patch, MagicMock

from ai_code_assistant.config import Config
from ai_code_assistant.llm import LLMManager


class TestLLMManager:
    """Tests for LLMManager class."""
    
    @pytest.fixture
    def config(self):
        """Create a config for testing."""
        return Config()
    
    @pytest.fixture
    def manager(self, config):
        """Create an LLMManager instance."""
        return LLMManager(config)
    
    def test_initialization(self, manager, config):
        """Test manager initialization."""
        assert manager.config == config
        assert manager._llm is None
    
    def test_get_model_info(self, manager):
        """Test getting model information."""
        info = manager.get_model_info()
        
        assert "model" in info
        assert "base_url" in info
        assert "temperature" in info
        assert "max_tokens" in info
        assert info["model"] == "deepseek-coder:6.7b"
    
    @patch('ai_code_assistant.llm.ChatOllama')
    def test_llm_lazy_initialization(self, mock_ollama, manager):
        """Test LLM is lazily initialized."""
        mock_instance = MagicMock()
        mock_ollama.return_value = mock_instance
        
        # First access should create the instance
        llm = manager.llm
        assert mock_ollama.called
        
        # Second access should return the same instance
        mock_ollama.reset_mock()
        llm2 = manager.llm
        assert not mock_ollama.called
        assert llm is llm2
    
    @patch('ai_code_assistant.llm.ChatOllama')
    def test_invoke_without_system_prompt(self, mock_ollama, manager):
        """Test invoking LLM without system prompt."""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "Test response"
        mock_llm.invoke.return_value = mock_response
        mock_ollama.return_value = mock_llm
        
        result = manager.invoke("Test prompt")
        
        assert result == "Test response"
        mock_llm.invoke.assert_called_once()
        # Verify only one message (HumanMessage) was passed
        call_args = mock_llm.invoke.call_args[0][0]
        assert len(call_args) == 1
    
    @patch('ai_code_assistant.llm.ChatOllama')
    def test_invoke_with_system_prompt(self, mock_ollama, manager):
        """Test invoking LLM with system prompt."""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "Test response"
        mock_llm.invoke.return_value = mock_response
        mock_ollama.return_value = mock_llm
        
        result = manager.invoke("Test prompt", system_prompt="You are a helpful assistant")
        
        assert result == "Test response"
        # Verify two messages were passed (System + Human)
        call_args = mock_llm.invoke.call_args[0][0]
        assert len(call_args) == 2
    
    @patch('ai_code_assistant.llm.ChatOllama')
    def test_stream(self, mock_ollama, manager):
        """Test streaming LLM response."""
        mock_llm = MagicMock()
        mock_chunks = [MagicMock(content="Hello"), MagicMock(content=" World")]
        mock_llm.stream.return_value = iter(mock_chunks)
        mock_ollama.return_value = mock_llm
        
        chunks = list(manager.stream("Test prompt"))
        
        assert chunks == ["Hello", " World"]
    
    @patch('ai_code_assistant.llm.ChatOllama')
    def test_check_connection_success(self, mock_ollama, manager):
        """Test connection check when server is available."""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "ok"
        mock_llm.invoke.return_value = mock_response
        mock_ollama.return_value = mock_llm
        
        assert manager.check_connection() is True
    
    @patch('ai_code_assistant.llm.ChatOllama')
    def test_check_connection_failure(self, mock_ollama, manager):
        """Test connection check when server is unavailable."""
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = Exception("Connection refused")
        mock_ollama.return_value = mock_llm
        
        assert manager.check_connection() is False
    
    @patch('ai_code_assistant.llm.ChatOllama')
    def test_invoke_with_template(self, mock_ollama, manager):
        """Test invoking LLM with prompt template."""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "Generated code"
        mock_ollama.return_value = mock_llm
        
        mock_template = MagicMock()
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = mock_response
        mock_template.__or__ = MagicMock(return_value=mock_chain)
        
        result = manager.invoke_with_template(mock_template, code="print('hello')")
        
        assert result == "Generated code"

