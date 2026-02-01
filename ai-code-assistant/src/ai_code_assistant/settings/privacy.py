"""Privacy settings and data management for Cognify AI."""

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .manager import get_settings_manager


class PrivacySettings:
    """Manages privacy-related settings and data rights (GDPR compliance)."""

    def __init__(self):
        """Initialize privacy settings."""
        self.settings = get_settings_manager()
        self.cognify_dir = self.settings.cognify_dir

    def anonymize_path(self, path: str) -> str:
        """Anonymize a file path by hashing it.
        
        Args:
            path: The file path to anonymize
            
        Returns:
            Hashed path if anonymization is enabled, otherwise the original path
        """
        if self.settings.get("privacy.anonymize_paths", True):
            # Hash the path but keep extension for analytics
            path_obj = Path(path)
            extension = path_obj.suffix
            hashed = hashlib.sha256(path.encode()).hexdigest()[:16]
            return f"{hashed}{extension}"
        return path

    def get_consent_status(self) -> Dict[str, bool]:
        """Get current consent status for all telemetry options."""
        return {
            "telemetry_enabled": self.settings.is_telemetry_enabled(),
            "share_usage_stats": self.settings.get("telemetry.share_usage_stats", True),
            "share_error_reports": self.settings.get("telemetry.share_error_reports", True),
            "share_feature_usage": self.settings.get("telemetry.share_feature_usage", True),
            "analytics_enabled": self.settings.is_analytics_enabled(),
            "analytics_local_only": self.settings.get("analytics.local_only", True),
        }

    def update_consent(
        self,
        telemetry_enabled: Optional[bool] = None,
        share_usage_stats: Optional[bool] = None,
        share_error_reports: Optional[bool] = None,
        share_feature_usage: Optional[bool] = None,
        analytics_enabled: Optional[bool] = None,
    ) -> None:
        """Update consent settings.
        
        Args:
            telemetry_enabled: Master switch for telemetry
            share_usage_stats: Share usage statistics
            share_error_reports: Share error reports
            share_feature_usage: Share feature usage patterns
            analytics_enabled: Enable local analytics
        """
        if telemetry_enabled is not None:
            self.settings.set("telemetry.enabled", telemetry_enabled)
        if share_usage_stats is not None:
            self.settings.set("telemetry.share_usage_stats", share_usage_stats)
        if share_error_reports is not None:
            self.settings.set("telemetry.share_error_reports", share_error_reports)
        if share_feature_usage is not None:
            self.settings.set("telemetry.share_feature_usage", share_feature_usage)
        if analytics_enabled is not None:
            self.settings.set("analytics.enabled", analytics_enabled)

    def export_user_data(self, output_path: Optional[Path] = None) -> Path:
        """Export all user data to a JSON file (GDPR Article 20).
        
        Args:
            output_path: Custom output path. Defaults to ~/cognify_data_export.json
            
        Returns:
            Path to the exported file
        """
        output_path = output_path or Path.home() / "cognify_data_export.json"
        
        export_data: Dict[str, Any] = {
            "export_date": datetime.utcnow().isoformat(),
            "device_id": self.settings.device_id,
            "settings": self.settings.get_all_settings(),
            "analytics": self._export_analytics_data(),
        }
        
        with open(output_path, "w") as f:
            json.dump(export_data, f, indent=2, default=str)
        
        return output_path

    def _export_analytics_data(self) -> Dict[str, Any]:
        """Export analytics data from SQLite database."""
        db_path = self.cognify_dir / "analytics.db"
        if not db_path.exists():
            return {"message": "No analytics data found"}
        
        import sqlite3
        
        data: Dict[str, List[Dict]] = {"usage_events": [], "daily_stats": []}
        
        try:
            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                # Export usage events
                cursor = conn.execute("SELECT * FROM usage_events ORDER BY timestamp DESC LIMIT 1000")
                data["usage_events"] = [dict(row) for row in cursor.fetchall()]
                
                # Export daily stats
                cursor = conn.execute("SELECT * FROM daily_stats ORDER BY date DESC")
                data["daily_stats"] = [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            data["error"] = str(e)
        
        return data

    def delete_all_data(self, confirm: bool = False) -> bool:
        """Delete all local user data (GDPR Article 17).
        
        Args:
            confirm: Must be True to actually delete data
            
        Returns:
            True if data was deleted, False otherwise
        """
        if not confirm:
            return False
        
        # Files to delete
        files_to_delete = [
            self.cognify_dir / "analytics.db",
            self.cognify_dir / "credentials.json",
            self.cognify_dir / "license.json",
        ]
        
        for file_path in files_to_delete:
            if file_path.exists():
                file_path.unlink()
        
        # Reset device ID (regenerate on next use)
        device_path = self.cognify_dir / "device.json"
        if device_path.exists():
            device_path.unlink()
        
        # Reset settings to defaults but keep the file
        self.settings._settings = self.settings.DEFAULT_SETTINGS.copy()
        self.settings._save_settings()
        
        return True

    def get_data_summary(self) -> Dict[str, Any]:
        """Get a summary of stored user data."""
        summary: Dict[str, Any] = {
            "device_id": self.settings.device_id,
            "config_file": str(self.settings.config_path),
            "data_directory": str(self.cognify_dir),
        }
        
        # Check analytics database
        db_path = self.cognify_dir / "analytics.db"
        if db_path.exists():
            import sqlite3
            try:
                with sqlite3.connect(db_path) as conn:
                    cursor = conn.execute("SELECT COUNT(*) FROM usage_events")
                    summary["total_events"] = cursor.fetchone()[0]
                    
                    cursor = conn.execute("SELECT MIN(timestamp), MAX(timestamp) FROM usage_events")
                    row = cursor.fetchone()
                    summary["data_range"] = {"from": row[0], "to": row[1]}
            except Exception:
                summary["analytics_db_error"] = True
        else:
            summary["total_events"] = 0
        
        return summary

