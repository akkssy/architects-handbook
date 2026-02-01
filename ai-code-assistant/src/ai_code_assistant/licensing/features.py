"""Feature flags and license tiers for Cognify AI."""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Set


class LicenseTier(str, Enum):
    """License tier levels."""
    FREE = "free"
    PRO = "pro"
    TEAM = "team"
    ENTERPRISE = "enterprise"


@dataclass
class TierLimits:
    """Limits for a license tier."""
    daily_cloud_llm_calls: int  # -1 for unlimited
    daily_local_llm_calls: int  # -1 for unlimited
    max_agents: int
    max_knowledge_base_projects: int
    max_knowledge_base_files: int
    max_codebase_files: int
    history_retention_days: int
    cloud_sync_enabled: bool
    team_features_enabled: bool
    custom_agents_enabled: bool


# Tier configurations
TIER_LIMITS: Dict[LicenseTier, TierLimits] = {
    LicenseTier.FREE: TierLimits(
        daily_cloud_llm_calls=100,
        daily_local_llm_calls=-1,  # Unlimited local
        max_agents=2,
        max_knowledge_base_projects=1,
        max_knowledge_base_files=1000,
        max_codebase_files=5000,
        history_retention_days=7,
        cloud_sync_enabled=False,
        team_features_enabled=False,
        custom_agents_enabled=False,
    ),
    LicenseTier.PRO: TierLimits(
        daily_cloud_llm_calls=-1,  # Unlimited
        daily_local_llm_calls=-1,
        max_agents=5,
        max_knowledge_base_projects=5,
        max_knowledge_base_files=10000,
        max_codebase_files=50000,
        history_retention_days=90,
        cloud_sync_enabled=True,
        team_features_enabled=False,
        custom_agents_enabled=True,
    ),
    LicenseTier.TEAM: TierLimits(
        daily_cloud_llm_calls=-1,
        daily_local_llm_calls=-1,
        max_agents=5,
        max_knowledge_base_projects=-1,
        max_knowledge_base_files=100000,
        max_codebase_files=500000,
        history_retention_days=365,
        cloud_sync_enabled=True,
        team_features_enabled=True,
        custom_agents_enabled=True,
    ),
    LicenseTier.ENTERPRISE: TierLimits(
        daily_cloud_llm_calls=-1,
        daily_local_llm_calls=-1,
        max_agents=-1,
        max_knowledge_base_projects=-1,
        max_knowledge_base_files=-1,
        max_codebase_files=-1,
        history_retention_days=-1,
        cloud_sync_enabled=True,
        team_features_enabled=True,
        custom_agents_enabled=True,
    ),
}


class FeatureFlags:
    """Feature flag management based on license tier."""

    # Available agents by tier
    FREE_AGENTS = {"general", "reviewer"}
    PRO_AGENTS = {"general", "reviewer", "generator", "documentation", "test_writer"}
    
    def __init__(self, tier: LicenseTier = LicenseTier.FREE):
        """Initialize feature flags for a tier."""
        self.tier = tier
        self.limits = TIER_LIMITS.get(tier, TIER_LIMITS[LicenseTier.FREE])

    def get_available_agents(self) -> Set[str]:
        """Get set of available agents for current tier."""
        if self.tier == LicenseTier.FREE:
            return self.FREE_AGENTS
        return self.PRO_AGENTS

    def is_agent_available(self, agent_id: str) -> bool:
        """Check if an agent is available for current tier."""
        return agent_id in self.get_available_agents()

    def can_use_cloud_llm(self, calls_today: int) -> bool:
        """Check if user can make a cloud LLM call."""
        limit = self.limits.daily_cloud_llm_calls
        return limit == -1 or calls_today < limit

    def can_use_feature(self, feature: str) -> bool:
        """Check if a feature is available for current tier."""
        feature_requirements: Dict[str, LicenseTier] = {
            "cloud_sync": LicenseTier.PRO,
            "team_sharing": LicenseTier.TEAM,
            "custom_agents": LicenseTier.PRO,
            "sso": LicenseTier.ENTERPRISE,
            "self_hosted": LicenseTier.ENTERPRISE,
        }
        
        required_tier = feature_requirements.get(feature)
        if required_tier is None:
            return True  # Feature not restricted
        
        tier_order = [LicenseTier.FREE, LicenseTier.PRO, LicenseTier.TEAM, LicenseTier.ENTERPRISE]
        return tier_order.index(self.tier) >= tier_order.index(required_tier)

    def get_remaining_calls(self, calls_today: int) -> Optional[int]:
        """Get remaining cloud LLM calls for today.
        
        Returns:
            Number of remaining calls, or None if unlimited
        """
        limit = self.limits.daily_cloud_llm_calls
        if limit == -1:
            return None
        # Defensive check: ensure calls_today is a valid integer
        if calls_today is None:
            calls_today = 0
        return max(0, limit - calls_today)

    def get_tier_info(self) -> Dict:
        """Get information about current tier and limits."""
        return {
            "tier": self.tier.value,
            "limits": {
                "daily_cloud_llm_calls": self.limits.daily_cloud_llm_calls,
                "daily_local_llm_calls": self.limits.daily_local_llm_calls,
                "max_agents": self.limits.max_agents,
                "history_retention_days": self.limits.history_retention_days,
            },
            "features": {
                "cloud_sync": self.limits.cloud_sync_enabled,
                "team_features": self.limits.team_features_enabled,
                "custom_agents": self.limits.custom_agents_enabled,
            },
            "available_agents": list(self.get_available_agents()),
        }

