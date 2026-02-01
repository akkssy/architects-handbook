"""
AI Code Assistant (Cognify AI) - An AI-powered code reviewer and generator.

Uses LangChain for orchestration and supports multiple LLM providers:
- Ollama (local)
- OpenAI
- Google Gemini
- Groq
"""

__version__ = "0.4.0"
__author__ = "Ashok"

from ai_code_assistant.config import Config, load_config
from ai_code_assistant.llm import LLMManager

__all__ = ["Config", "load_config", "LLMManager", "__version__"]

