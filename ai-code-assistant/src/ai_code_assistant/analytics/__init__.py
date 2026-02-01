"""Analytics collection and storage module."""

from .collector import AnalyticsCollector, get_collector, track_event
from .storage import AnalyticsStorage

__all__ = ["AnalyticsCollector", "get_collector", "track_event", "AnalyticsStorage"]

