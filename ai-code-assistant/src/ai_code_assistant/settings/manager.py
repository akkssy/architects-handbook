"""Settings manager for Cognify AI user preferences and configuration."""

import json
import uuid
from pathlib import Path
from typing import Any, Dict, Optional
from datetime import datetime

import yaml


class SettingsManager:
    """Manages user settings and preferences with configurable features."""

    DEFAULT_SETTINGS = {
        "version": "1.0.0",
        "telemetry": {
            "enabled": True,  # Master switch for all telemetry
            "share_usage_stats": True,  # Share command usage statistics
            "share_error_reports": True,  # Share error reports
            "share_feature_usage": True,  # Share feature usage patterns
        },
        "analytics": {
            "enabled": True,  # Local analytics collection
            "local_only": True,  # Don't sync to cloud (for now)
            "retention_days": 90,  # How long to keep local data
        },
        "authentication": {
            "enabled": False,  # Authentication is optional
            "auto_login": False,  # Auto-login on startup
        },
        "licensing": {
            "tier": "free",  # Current license tier
            "offline_mode": True,  # Work offline without validation
        },
        "privacy": {
            "anonymize_paths": True,  # Hash file paths instead of storing raw
            "collect_code_metrics": False,  # Collect code complexity metrics (no actual code)
        },
    }

    def __init__(self, cognify_dir: Optional[Path] = None):
        """Initialize settings manager.
        
        Args:
            cognify_dir: Custom directory for Cognify data. Defaults to ~/.cognify/
        """
        self.cognify_dir = cognify_dir or Path.home() / ".cognify"
        self.cognify_dir.mkdir(parents=True, exist_ok=True)
        
        self.config_path = self.cognify_dir / "config.yaml"
        self.device_path = self.cognify_dir / "device.json"
        
        self._settings: Dict[str, Any] = {}
        self._device_id: Optional[str] = None
        
        self._load_settings()
        self._ensure_device_id()

    def _load_settings(self) -> None:
        """Load settings from config file or create defaults."""
        if self.config_path.exists():
            try:
                with open(self.config_path, "r") as f:
                    loaded = yaml.safe_load(f) or {}
                # Merge with defaults to ensure all keys exist
                self._settings = self._deep_merge(self.DEFAULT_SETTINGS.copy(), loaded)
            except Exception:
                self._settings = self.DEFAULT_SETTINGS.copy()
        else:
            self._settings = self.DEFAULT_SETTINGS.copy()
            self._save_settings()

    def _save_settings(self) -> None:
        """Save settings to config file."""
        with open(self.config_path, "w") as f:
            yaml.dump(self._settings, f, default_flow_style=False, sort_keys=False)

    def _deep_merge(self, base: Dict, override: Dict) -> Dict:
        """Deep merge two dictionaries."""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def _ensure_device_id(self) -> None:
        """Ensure device ID exists or create one."""
        if self.device_path.exists():
            try:
                data = json.loads(self.device_path.read_text())
                self._device_id = data.get("device_id")
            except Exception:
                pass
        
        if not self._device_id:
            self._device_id = str(uuid.uuid4())
            device_data = {
                "device_id": self._device_id,
                "created_at": datetime.utcnow().isoformat(),
                "platform": self._get_platform_info(),
            }
            self.device_path.write_text(json.dumps(device_data, indent=2))

    def _get_platform_info(self) -> Dict[str, str]:
        """Get anonymous platform information."""
        import platform
        return {
            "system": platform.system(),
            "python_version": platform.python_version(),
        }

    @property
    def device_id(self) -> str:
        """Get the device ID."""
        return self._device_id or ""

    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value using dot notation (e.g., 'telemetry.enabled')."""
        keys = key.split(".")
        value = self._settings
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
            if value is None:
                return default
        return value

    def set(self, key: str, value: Any) -> None:
        """Set a setting value using dot notation."""
        keys = key.split(".")
        current = self._settings
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]
        current[keys[-1]] = value
        self._save_settings()

    # Convenience methods for checking feature states
    def is_telemetry_enabled(self) -> bool:
        """Check if telemetry is enabled."""
        return bool(self.get("telemetry.enabled", True))

    def is_analytics_enabled(self) -> bool:
        """Check if local analytics collection is enabled."""
        return bool(self.get("analytics.enabled", True))

    def is_auth_enabled(self) -> bool:
        """Check if authentication is enabled."""
        return bool(self.get("authentication.enabled", False))

    def get_license_tier(self) -> str:
        """Get the current license tier."""
        return str(self.get("licensing.tier", "free"))

    def get_all_settings(self) -> Dict[str, Any]:
        """Get all settings as a dictionary."""
        return self._settings.copy()


# Global instance
_settings_manager: Optional[SettingsManager] = None


def get_settings_manager() -> SettingsManager:
    """Get the global settings manager instance."""
    global _settings_manager
    if _settings_manager is None:
        _settings_manager = SettingsManager()
    return _settings_manager

