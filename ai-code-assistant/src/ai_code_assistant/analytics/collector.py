"""Analytics collector with configurable tracking."""

import functools
import time
import uuid
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Callable, Dict, Generator, Optional, TypeVar

from ..settings import get_settings_manager
from .storage import AnalyticsStorage

F = TypeVar("F", bound=Callable[..., Any])


class AnalyticsCollector:
    """Collects and stores usage analytics with configurable tracking.
    
    All tracking methods check if analytics is enabled before collecting data.
    If disabled, methods return immediately without any side effects.
    """

    def __init__(self):
        """Initialize analytics collector."""
        self.settings = get_settings_manager()
        self._storage: Optional[AnalyticsStorage] = None
        self._session_id = str(uuid.uuid4())
        self._session_start = datetime.utcnow()

    @property
    def storage(self) -> AnalyticsStorage:
        """Lazy-load storage to avoid creating DB when disabled."""
        if self._storage is None:
            db_path = self.settings.cognify_dir / "analytics.db"
            self._storage = AnalyticsStorage(db_path)
        return self._storage

    def is_enabled(self) -> bool:
        """Check if analytics collection is enabled."""
        return self.settings.is_analytics_enabled()

    def track_command(
        self,
        command: str,
        duration_ms: int,
        success: bool = True,
        client: str = "cli",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Track a command execution.
        
        Args:
            command: Command name (e.g., 'smart-chat', 'review')
            duration_ms: Execution time in milliseconds
            success: Whether command succeeded
            client: Client type ('cli' or 'vscode')
            metadata: Additional metadata (no sensitive data!)
        """
        if not self.is_enabled():
            return
        
        try:
            self.storage.insert_event(
                event_type="command",
                event_name=command,
                duration_ms=duration_ms,
                success=success,
                client=client,
                session_id=self._session_id,
                metadata=metadata,
            )
        except Exception:
            # Never let analytics errors break the application
            pass

    def track_llm_call(
        self,
        provider: str,
        model: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        latency_ms: int = 0,
        cost_estimate: float = 0.0,
        client: str = "cli",
    ) -> None:
        """Track an LLM API call.
        
        Args:
            provider: LLM provider (e.g., 'ollama', 'google', 'openai')
            model: Model name
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            latency_ms: Response latency in milliseconds
            cost_estimate: Estimated cost in USD
            client: Client type
        """
        if not self.is_enabled():
            return
        
        try:
            # Track in token_usage table
            self.storage.insert_token_usage(
                provider=provider,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_estimate=cost_estimate,
                latency_ms=latency_ms,
            )
            
            # Also track as event for general analytics
            self.storage.insert_event(
                event_type="llm_call",
                event_name=f"{provider}/{model}",
                duration_ms=latency_ms,
                success=True,
                client=client,
                session_id=self._session_id,
                metadata={
                    "provider": provider,
                    "model": model,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                },
            )
        except Exception:
            pass

    def track_feature(
        self,
        feature: str,
        client: str = "cli",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Track feature usage.
        
        Args:
            feature: Feature name (e.g., 'knowledge_base', 'codebase_search')
            client: Client type
            metadata: Additional metadata
        """
        if not self.is_enabled():
            return
        
        if not self.settings.get("telemetry.share_feature_usage", True):
            return
        
        try:
            self.storage.insert_event(
                event_type="feature",
                event_name=feature,
                client=client,
                session_id=self._session_id,
                metadata=metadata,
            )
        except Exception:
            pass

    def track_error(
        self,
        error_type: str,
        error_message: str,
        command: Optional[str] = None,
        client: str = "cli",
    ) -> None:
        """Track an error occurrence.

        Args:
            error_type: Type of error (e.g., 'LLMError', 'ConfigError')
            error_message: Error message (sanitized, no sensitive data!)
            command: Command that caused the error
            client: Client type
        """
        if not self.is_enabled():
            return

        if not self.settings.get("telemetry.share_error_reports", True):
            return

        try:
            self.storage.insert_event(
                event_type="error",
                event_name=error_type,
                success=False,
                client=client,
                session_id=self._session_id,
                metadata={
                    "message": error_message[:200],  # Truncate long messages
                    "command": command,
                },
            )
        except Exception:
            pass

    @contextmanager
    def track_command_context(
        self,
        command: str,
        client: str = "cli",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Generator[None, None, None]:
        """Context manager for tracking command execution.

        Usage:
            with collector.track_command_context("smart-chat"):
                # command code here
        """
        start_time = time.time()
        success = True
        try:
            yield
        except Exception as e:
            success = False
            self.track_error(
                error_type=type(e).__name__,
                error_message=str(e),
                command=command,
                client=client,
            )
            raise
        finally:
            duration_ms = int((time.time() - start_time) * 1000)
            self.track_command(
                command=command,
                duration_ms=duration_ms,
                success=success,
                client=client,
                metadata=metadata,
            )

    def get_usage_today(self) -> Dict[str, int]:
        """Get today's usage statistics."""
        if not self.is_enabled():
            return {"commands_today": 0, "llm_calls_today": 0}
        try:
            return self.storage.get_usage_today()
        except Exception:
            return {"commands_today": 0, "llm_calls_today": 0}

    def get_daily_stats(self, days: int = 7) -> list:
        """Get daily statistics."""
        if not self.is_enabled():
            return []
        try:
            return self.storage.get_daily_stats(days)
        except Exception:
            return []

    def get_summary(self) -> Dict[str, Any]:
        """Get analytics summary."""
        if not self.is_enabled():
            return {"analytics_enabled": False}
        try:
            summary = self.storage.get_summary()
            summary["analytics_enabled"] = True
            return summary
        except Exception:
            return {"analytics_enabled": True, "error": "Failed to get summary"}


# Global instance
_collector: Optional[AnalyticsCollector] = None


def get_collector() -> AnalyticsCollector:
    """Get the global analytics collector instance."""
    global _collector
    if _collector is None:
        _collector = AnalyticsCollector()
    return _collector


def track_event(
    event_type: str,
    event_name: str,
    duration_ms: Optional[int] = None,
    success: bool = True,
    client: str = "cli",
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Convenience function to track a generic event."""
    collector = get_collector()
    if not collector.is_enabled():
        return
    try:
        collector.storage.insert_event(
            event_type=event_type,
            event_name=event_name,
            duration_ms=duration_ms,
            success=success,
            client=client,
            session_id=collector._session_id,
            metadata=metadata,
        )
    except Exception:
        pass


def track_command_decorator(command_name: Optional[str] = None, client: str = "cli") -> Callable[[F], F]:
    """Decorator to track command execution.

    Usage:
        @track_command_decorator()
        def my_command():
            ...

        @track_command_decorator("custom-name")
        def another_command():
            ...
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            collector = get_collector()
            name = command_name or func.__name__

            with collector.track_command_context(name, client=client):
                return func(*args, **kwargs)

        return wrapper  # type: ignore

    return decorator

