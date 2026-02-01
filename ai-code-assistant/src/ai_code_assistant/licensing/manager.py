"""License manager for Cognify AI."""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

from ..settings import get_settings_manager
from ..analytics import get_collector
from .features import FeatureFlags, LicenseTier, TIER_LIMITS


class LicenseManager:
    """Manages license validation and feature access.
    
    This is a local-first implementation that:
    - Works offline by default (free tier)
    - Caches license information locally
    - Validates against server periodically (future)
    - Degrades gracefully when offline
    """

    def __init__(self):
        """Initialize license manager."""
        self.settings = get_settings_manager()
        self.license_path = self.settings.cognify_dir / "license.json"
        self._license_data: Optional[Dict[str, Any]] = None
        self._feature_flags: Optional[FeatureFlags] = None
        self._load_license()

    def _load_license(self) -> None:
        """Load cached license data from disk."""
        if self.license_path.exists():
            try:
                self._license_data = json.loads(self.license_path.read_text())
            except Exception:
                self._license_data = None

    def _save_license(self) -> None:
        """Save license data to disk."""
        if self._license_data:
            self.license_path.write_text(json.dumps(self._license_data, indent=2))

    def get_tier(self) -> LicenseTier:
        """Get current license tier."""
        tier_str = self.settings.get_license_tier()
        try:
            return LicenseTier(tier_str)
        except ValueError:
            return LicenseTier.FREE

    def get_feature_flags(self) -> FeatureFlags:
        """Get feature flags for current tier."""
        if self._feature_flags is None or self._feature_flags.tier != self.get_tier():
            self._feature_flags = FeatureFlags(self.get_tier())
        return self._feature_flags

    def check_usage_limit(self, provider: str = "cloud") -> Dict[str, Any]:
        """Check if user is within usage limits.
        
        Args:
            provider: 'cloud' for cloud LLM providers, 'local' for Ollama
            
        Returns:
            Dict with 'allowed', 'remaining', and 'message' keys
        """
        flags = self.get_feature_flags()
        collector = get_collector()
        
        # Local providers (Ollama) are always unlimited
        if provider == "local" or provider == "ollama":
            return {
                "allowed": True,
                "remaining": None,
                "message": "Local LLM usage is unlimited",
            }
        
        # Check cloud LLM usage
        usage = collector.get_usage_today()
        calls_today = usage.get("llm_calls_today", 0)
        
        if flags.can_use_cloud_llm(calls_today):
            remaining = flags.get_remaining_calls(calls_today)
            return {
                "allowed": True,
                "remaining": remaining,
                "message": f"Remaining calls today: {remaining}" if remaining else "Unlimited",
            }
        else:
            limit = flags.limits.daily_cloud_llm_calls
            return {
                "allowed": False,
                "remaining": 0,
                "message": f"Daily limit of {limit} cloud LLM calls reached. "
                           f"Upgrade to Pro for unlimited usage or use local Ollama.",
            }

    def is_feature_available(self, feature: str) -> bool:
        """Check if a feature is available."""
        return self.get_feature_flags().can_use_feature(feature)

    def is_agent_available(self, agent_id: str) -> bool:
        """Check if an agent is available for current tier."""
        return self.get_feature_flags().is_agent_available(agent_id)

    def get_license_status(self) -> Dict[str, Any]:
        """Get comprehensive license status."""
        tier = self.get_tier()
        flags = self.get_feature_flags()
        collector = get_collector()
        usage = collector.get_usage_today()
        
        status = {
            "tier": tier.value,
            "tier_display": tier.value.title(),
            "is_paid": tier != LicenseTier.FREE,
            "usage_today": usage,
            "limits": flags.get_tier_info()["limits"],
            "features": flags.get_tier_info()["features"],
        }
        
        # Add remaining calls info
        calls_today = usage.get("llm_calls_today", 0)
        remaining = flags.get_remaining_calls(calls_today)
        status["remaining_cloud_calls"] = remaining
        
        # Add license expiry if applicable
        if self._license_data:
            status["license_key_active"] = True
            if "expires_at" in self._license_data:
                status["expires_at"] = self._license_data["expires_at"]
        else:
            status["license_key_active"] = False
        
        return status

    def activate_license(self, license_key: str) -> Dict[str, Any]:
        """Activate a license key (placeholder for future server validation).
        
        Args:
            license_key: License key to activate
            
        Returns:
            Activation result with success status and message
        """
        # For Phase 1, we do basic local validation
        # Full server validation will be added in Phase 3
        
        if not license_key or len(license_key) < 10:
            return {
                "success": False,
                "message": "Invalid license key format",
            }
        
        # Parse license key format: COGN-TIER-YEAR-XXXX-XXXX-XXXX-XXXX
        parts = license_key.upper().split("-")
        if len(parts) < 3 or parts[0] != "COGN":
            return {
                "success": False,
                "message": "Invalid license key format. Expected: COGN-TIER-...",
            }
        
        tier_map = {"FREE": "free", "PRO": "pro", "TEAM": "team", "ENT": "enterprise"}
        tier_code = parts[1]
        
        if tier_code not in tier_map:
            return {
                "success": False,
                "message": f"Unknown license tier: {tier_code}",
            }
        
        # Store license data
        self._license_data = {
            "key": license_key,
            "tier": tier_map[tier_code],
            "activated_at": datetime.utcnow().isoformat(),
            "expires_at": (datetime.utcnow() + timedelta(days=365)).isoformat(),
        }
        self._save_license()
        
        # Update settings
        self.settings.set("licensing.tier", tier_map[tier_code])
        
        return {
            "success": True,
            "message": f"License activated successfully! Tier: {tier_map[tier_code].title()}",
            "tier": tier_map[tier_code],
        }


# Global instance
_license_manager: Optional[LicenseManager] = None


def get_license_manager() -> LicenseManager:
    """Get the global license manager instance."""
    global _license_manager
    if _license_manager is None:
        _license_manager = LicenseManager()
    return _license_manager

