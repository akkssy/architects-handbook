"""Interactive chat session for code discussions."""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Literal, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from ai_code_assistant.config import Config
from ai_code_assistant.llm import LLMManager


@dataclass
class Message:
    """A single message in the chat history."""
    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    code_context: Optional[str] = None


CHAT_SYSTEM_PROMPT = """You are an expert programming assistant with deep knowledge of software development.

You can help with:
- Explaining code and concepts
- Debugging issues
- Suggesting improvements
- Answering programming questions
- Discussing architecture and design patterns

When discussing code:
- Be clear and concise
- Provide code examples when helpful
- Explain your reasoning
- Consider edge cases and best practices

If code context is provided, reference it in your responses when relevant."""


class ChatSession:
    """Manages an interactive chat session."""

    def __init__(
        self,
        config: Config,
        llm_manager: LLMManager,
        system_prompt: Optional[str] = None,
    ):
        self.config = config
        self.llm = llm_manager
        self.system_prompt = system_prompt or CHAT_SYSTEM_PROMPT
        self.history: List[Message] = []
        self._code_context: Dict[str, str] = {}  # filename -> code

    def add_code_context(self, filename: str, code: str) -> None:
        """Add code file to the conversation context."""
        self._code_context[filename] = code

    def load_file_context(self, file_path: Path) -> bool:
        """Load a file into the conversation context."""
        try:
            code = file_path.read_text()
            self.add_code_context(str(file_path), code)
            return True
        except Exception:
            return False

    def clear_context(self) -> None:
        """Clear all code context."""
        self._code_context.clear()

    def send_message(self, user_input: str, stream: bool = False):
        """Send a message and get a response."""
        # Add user message to history
        self.history.append(Message(role="user", content=user_input))

        # Build messages for LLM
        messages = self._build_messages(user_input)

        if stream:
            return self._stream_response(messages)
        else:
            return self._get_response(messages)

    def _build_messages(self, current_input: str) -> List:
        """Build message list for LLM including context and history."""
        messages = []
        
        # System message with code context
        system_content = self.system_prompt
        if self._code_context:
            context_str = "\n\n".join(
                f"**File: {name}**\n```\n{code}\n```"
                for name, code in self._code_context.items()
            )
            system_content += f"\n\n**Code Context:**\n{context_str}"
        
        messages.append(SystemMessage(content=system_content))
        
        # Add conversation history (keep last N messages to manage context window)
        max_history = 20
        recent_history = self.history[-(max_history + 1):-1]  # Exclude current message
        
        for msg in recent_history:
            if msg.role == "user":
                messages.append(HumanMessage(content=msg.content))
            elif msg.role == "assistant":
                messages.append(AIMessage(content=msg.content))
        
        # Add current message
        messages.append(HumanMessage(content=current_input))
        
        return messages

    def _get_response(self, messages: List) -> str:
        """Get complete response from LLM."""
        response = self.llm.llm.invoke(messages)
        content = str(response.content)
        
        # Add assistant response to history
        self.history.append(Message(role="assistant", content=content))
        
        return content

    def _stream_response(self, messages: List):
        """Stream response from LLM."""
        full_response = []
        
        for chunk in self.llm.llm.stream(messages):
            chunk_content = str(chunk.content)
            full_response.append(chunk_content)
            yield chunk_content
        
        # Add complete response to history
        self.history.append(Message(role="assistant", content="".join(full_response)))

    def get_history(self) -> List[Message]:
        """Get conversation history."""
        return self.history.copy()

    def clear_history(self) -> None:
        """Clear conversation history."""
        self.history.clear()

    def export_history(self) -> str:
        """Export conversation history as markdown."""
        lines = ["# Chat Session\n"]
        
        if self._code_context:
            lines.append("## Code Context\n")
            for name in self._code_context:
                lines.append(f"- {name}")
            lines.append("")
        
        lines.append("## Conversation\n")
        for msg in self.history:
            timestamp = msg.timestamp.strftime("%H:%M:%S")
            role = "**You**" if msg.role == "user" else "**Assistant**"
            lines.append(f"### {role} ({timestamp})\n")
            lines.append(msg.content)
            lines.append("")
        
        return "\n".join(lines)

