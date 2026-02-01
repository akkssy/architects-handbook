"""Authentication manager for Cognify AI.

This is a Phase 1 placeholder that provides basic structure.
Full OAuth implementation will be added in Phase 2.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from ..settings import get_settings_manager


class AuthManager:
    """Manages user authentication and credentials.
    
    Phase 1: Basic local-only authentication status
    Phase 2: Full OAuth with GitHub/Google
    """

    def __init__(self):
        """Initialize auth manager."""
        self.settings = get_settings_manager()
        self.credentials_path = self.settings.cognify_dir / "credentials.json"
        self._user_data: Optional[Dict[str, Any]] = None
        self._load_credentials()

    def _load_credentials(self) -> None:
        """Load stored credentials."""
        if self.credentials_path.exists():
            try:
                # In Phase 2, this will be encrypted
                self._user_data = json.loads(self.credentials_path.read_text())
            except Exception:
                self._user_data = None

    def _save_credentials(self) -> None:
        """Save credentials to disk."""
        if self._user_data:
            # In Phase 2, this will be encrypted
            self.credentials_path.write_text(json.dumps(self._user_data, indent=2))
        elif self.credentials_path.exists():
            self.credentials_path.unlink()

    def is_enabled(self) -> bool:
        """Check if authentication is enabled."""
        return self.settings.is_auth_enabled()

    def is_authenticated(self) -> bool:
        """Check if user is currently authenticated."""
        if not self.is_enabled():
            return False  # Auth not required
        return self._user_data is not None and "user_id" in self._user_data

    def get_current_user(self) -> Optional[Dict[str, Any]]:
        """Get current authenticated user info."""
        if not self.is_authenticated():
            return None
        return {
            "user_id": self._user_data.get("user_id"),
            "email": self._user_data.get("email"),
            "name": self._user_data.get("name"),
            "authenticated_at": self._user_data.get("authenticated_at"),
        }

    def get_auth_status(self) -> Dict[str, Any]:
        """Get comprehensive authentication status."""
        status = {
            "auth_enabled": self.is_enabled(),
            "is_authenticated": self.is_authenticated(),
            "device_id": self.settings.device_id,
        }
        
        if self.is_authenticated():
            status["user"] = self.get_current_user()
        else:
            status["message"] = (
                "Authentication not configured. "
                "Run 'cognify auth login' to authenticate (optional)."
                if self.is_enabled()
                else "Authentication is disabled. Enable in settings if needed."
            )
        
        return status

    def login_with_api_key(self, api_key: str) -> Dict[str, Any]:
        """Login with an API key (Phase 1 placeholder).
        
        Full implementation in Phase 2 will validate against server.
        """
        if not api_key or len(api_key) < 10:
            return {
                "success": False,
                "message": "Invalid API key format",
            }
        
        # Phase 1: Basic local storage
        # Phase 2: Server validation
        self._user_data = {
            "user_id": f"api_key_{api_key[:8]}",
            "api_key": api_key,
            "authenticated_at": datetime.utcnow().isoformat(),
            "method": "api_key",
        }
        self._save_credentials()
        
        # Enable auth in settings
        self.settings.set("authentication.enabled", True)
        
        return {
            "success": True,
            "message": "API key stored successfully",
            "user_id": self._user_data["user_id"],
        }

    def logout(self) -> Dict[str, Any]:
        """Logout current user."""
        if not self.is_authenticated():
            return {
                "success": False,
                "message": "Not currently authenticated",
            }
        
        self._user_data = None
        self._save_credentials()
        
        return {
            "success": True,
            "message": "Logged out successfully",
        }

    def login_oauth(self, provider: str = "github") -> Dict[str, Any]:
        """Initiate OAuth login flow (Phase 2 placeholder).
        
        Args:
            provider: OAuth provider ('github', 'google')
        """
        return {
            "success": False,
            "message": f"OAuth login with {provider} will be available in a future update. "
                       f"For now, use API key authentication or disable authentication.",
        }


# Global instance
_auth_manager: Optional[AuthManager] = None


def get_auth_manager() -> AuthManager:
    """Get the global auth manager instance."""
    global _auth_manager
    if _auth_manager is None:
        _auth_manager = AuthManager()
    return _auth_manager

