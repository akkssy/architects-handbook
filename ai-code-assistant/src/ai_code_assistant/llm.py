"""LLM Manager for Ollama integration via LangChain."""

from typing import Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama

from ai_code_assistant.config import Config


class LLMManager:
    """Manages LLM interactions using LangChain and Ollama."""

    def __init__(self, config: Config):
        """Initialize LLM manager with configuration."""
        self.config = config
        self._llm: Optional[BaseChatModel] = None

    @property
    def llm(self) -> BaseChatModel:
        """Get or create the LLM instance."""
        if self._llm is None:
            self._llm = ChatOllama(
                model=self.config.llm.model,
                base_url=self.config.llm.base_url,
                temperature=self.config.llm.temperature,
                num_predict=self.config.llm.max_tokens,
                timeout=self.config.llm.timeout,
            )
        return self._llm

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
        """Check if Ollama server is accessible."""
        try:
            # Simple test query
            self.invoke("Say 'ok' and nothing else.")
            return True
        except Exception:
            return False

    def get_model_info(self) -> dict:
        """Get information about the current model configuration."""
        return {
            "model": self.config.llm.model,
            "base_url": self.config.llm.base_url,
            "temperature": self.config.llm.temperature,
            "max_tokens": self.config.llm.max_tokens,
        }

