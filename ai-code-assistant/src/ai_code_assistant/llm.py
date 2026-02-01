"""LLM Manager for multiple provider integration via LangChain."""

import os
from typing import Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate

from ai_code_assistant.config import Config


class LLMManager:
    """Manages LLM interactions using LangChain with multiple providers."""

    # Provider URL mappings
    PROVIDER_URLS = {
        "ollama": "http://localhost:11434",
        "openai": "https://api.openai.com/v1",
        "google": "https://generativelanguage.googleapis.com/v1beta",
        "groq": "https://api.groq.com/openai/v1",
    }

    def __init__(self, config: Config, provider: Optional[str] = None, model: Optional[str] = None):
        """Initialize LLM manager with configuration and optional overrides."""
        self.config = config
        self._llm: Optional[BaseChatModel] = None
        # Allow runtime override of provider and model
        self._provider_override = provider
        self._model_override = model

    @property
    def provider(self) -> str:
        """Get the current provider (override or config)."""
        return self._provider_override or getattr(self.config.llm, 'provider', 'ollama')

    @property
    def model(self) -> str:
        """Get the current model (override or config)."""
        return self._model_override or self.config.llm.model

    @property
    def llm(self) -> BaseChatModel:
        """Get or create the LLM instance based on provider."""
        if self._llm is None:
            self._llm = self._create_llm()
        return self._llm

    def _create_llm(self) -> BaseChatModel:
        """Create the appropriate LLM based on provider."""
        provider = self.provider.lower()
        model = self.model

        if provider == "ollama":
            return self._create_ollama_llm(model)
        elif provider == "openai":
            return self._create_openai_llm(model)
        elif provider == "google":
            return self._create_google_llm(model)
        elif provider == "groq":
            return self._create_groq_llm(model)
        else:
            # Default to Ollama for unknown providers
            return self._create_ollama_llm(model)

    def _create_ollama_llm(self, model: str) -> BaseChatModel:
        """Create Ollama LLM instance."""
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=model,
            base_url=self.config.llm.base_url or self.PROVIDER_URLS["ollama"],
            temperature=self.config.llm.temperature,
            num_predict=self.config.llm.max_tokens,
            timeout=self.config.llm.timeout,
        )

    def _create_openai_llm(self, model: str) -> BaseChatModel:
        """Create OpenAI LLM instance."""
        from langchain_openai import ChatOpenAI
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        return ChatOpenAI(
            model=model,
            api_key=api_key,
            temperature=self.config.llm.temperature,
            max_tokens=self.config.llm.max_tokens,
            timeout=self.config.llm.timeout,
        )

    def _create_google_llm(self, model: str) -> BaseChatModel:
        """Create Google Gemini LLM instance."""
        from langchain_google_genai import ChatGoogleGenerativeAI
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable not set")
        return ChatGoogleGenerativeAI(
            model=model,
            google_api_key=api_key,
            temperature=self.config.llm.temperature,
            max_output_tokens=self.config.llm.max_tokens,
        )

    def _create_groq_llm(self, model: str) -> BaseChatModel:
        """Create Groq LLM instance."""
        from langchain_groq import ChatGroq
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY environment variable not set")
        return ChatGroq(
            model=model,
            api_key=api_key,
            temperature=self.config.llm.temperature,
            max_tokens=self.config.llm.max_tokens,
        )

    def invoke(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Invoke the LLM with a prompt and optional system message."""
        messages = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(HumanMessage(content=prompt))
        
        response = self.llm.invoke(messages)
        return str(response.content)

    def invoke_with_template(
        self,
        template: ChatPromptTemplate,
        **kwargs,
    ) -> str:
        """Invoke the LLM using a prompt template."""
        chain = template | self.llm
        response = chain.invoke(kwargs)
        return str(response.content)

    def stream(self, prompt: str, system_prompt: Optional[str] = None):
        """Stream LLM response for real-time output."""
        messages = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(HumanMessage(content=prompt))
        
        for chunk in self.llm.stream(messages):
            yield str(chunk.content)

    def check_connection(self) -> bool:
        """Check if LLM is accessible."""
        try:
            # Simple test query
            self.invoke("Say 'ok' and nothing else.")
            return True
        except Exception:
            return False

    def get_model_info(self) -> dict:
        """Get information about the current model configuration."""
        return {
            "provider": self.provider,
            "model": self.model,
            "base_url": self.PROVIDER_URLS.get(self.provider.lower(), self.config.llm.base_url),
            "temperature": self.config.llm.temperature,
            "max_tokens": self.config.llm.max_tokens,
        }

