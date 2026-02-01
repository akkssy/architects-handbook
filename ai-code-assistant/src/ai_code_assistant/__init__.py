"""
AI Code Assistant - An AI-powered code reviewer and generator.

Uses LangChain for orchestration and Ollama for local LLM inference.
"""

__version__ = "0.1.0"
__author__ = "Developer"

from ai_code_assistant.config import Config, load_config
from ai_code_assistant.llm import LLMManager

__all__ = ["Config", "load_config", "LLMManager", "__version__"]

