"""Settings and privacy management module."""

from .manager import SettingsManager, get_settings_manager
from .privacy import PrivacySettings

__all__ = ["SettingsManager", "get_settings_manager", "PrivacySettings"]

