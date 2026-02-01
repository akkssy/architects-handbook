"""SQLite storage for analytics data."""

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional


class AnalyticsStorage:
    """SQLite-based storage for usage analytics."""

    SCHEMA_VERSION = 1

    def __init__(self, db_path: Path):
        """Initialize analytics storage.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._local = threading.local()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._local, "connection"):
            self._local.connection = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                timeout=30.0
            )
            self._local.connection.row_factory = sqlite3.Row
        return self._local.connection

    @contextmanager
    def _transaction(self) -> Generator[sqlite3.Cursor, None, None]:
        """Context manager for database transactions."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def _init_db(self) -> None:
        """Initialize database schema."""
        with self._transaction() as cursor:
            # Schema version tracking
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS schema_info (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            
            # Usage events table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS usage_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    event_name TEXT NOT NULL,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                    duration_ms INTEGER,
                    success INTEGER DEFAULT 1,
                    client TEXT,
                    session_id TEXT,
                    metadata TEXT,
                    synced INTEGER DEFAULT 0
                )
            """)
            
            # Token usage tracking
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS token_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    input_tokens INTEGER DEFAULT 0,
                    output_tokens INTEGER DEFAULT 0,
                    cost_estimate REAL DEFAULT 0,
                    latency_ms INTEGER,
                    synced INTEGER DEFAULT 0
                )
            """)
            
            # Daily aggregates for quick stats
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS daily_stats (
                    date TEXT PRIMARY KEY,
                    total_commands INTEGER DEFAULT 0,
                    total_llm_calls INTEGER DEFAULT 0,
                    total_input_tokens INTEGER DEFAULT 0,
                    total_output_tokens INTEGER DEFAULT 0,
                    total_cost REAL DEFAULT 0,
                    active_minutes INTEGER DEFAULT 0,
                    providers_used TEXT,
                    models_used TEXT,
                    synced INTEGER DEFAULT 0
                )
            """)
            
            # Create indexes for performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_timestamp ON usage_events(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_type ON usage_events(event_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_synced ON usage_events(synced)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tokens_timestamp ON token_usage(timestamp)")
            
            # Store schema version
            cursor.execute(
                "INSERT OR REPLACE INTO schema_info (key, value) VALUES (?, ?)",
                ("version", str(self.SCHEMA_VERSION))
            )

    def insert_event(
        self,
        event_type: str,
        event_name: str,
        duration_ms: Optional[int] = None,
        success: bool = True,
        client: str = "cli",
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Insert a usage event.
        
        Returns:
            The ID of the inserted event
        """
        with self._transaction() as cursor:
            cursor.execute(
                """INSERT INTO usage_events 
                   (event_type, event_name, duration_ms, success, client, session_id, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    event_type,
                    event_name,
                    duration_ms,
                    1 if success else 0,
                    client,
                    session_id,
                    json.dumps(metadata) if metadata else None,
                )
            )
            return cursor.lastrowid or 0

    def insert_token_usage(
        self,
        provider: str,
        model: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost_estimate: float = 0.0,
        latency_ms: Optional[int] = None,
    ) -> int:
        """Insert token usage record.
        
        Returns:
            The ID of the inserted record
        """
        with self._transaction() as cursor:
            cursor.execute(
                """INSERT INTO token_usage 
                   (provider, model, input_tokens, output_tokens, cost_estimate, latency_ms)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (provider, model, input_tokens, output_tokens, cost_estimate, latency_ms)
            )
            return cursor.lastrowid or 0

    def get_events(
        self,
        event_type: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get usage events with optional filtering."""
        query = "SELECT * FROM usage_events WHERE 1=1"
        params: List[Any] = []
        
        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)
        
        if since:
            query += " AND timestamp >= ?"
            params.append(since.isoformat())
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        conn = self._get_connection()
        cursor = conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def get_usage_today(self) -> Dict[str, int]:
        """Get today's usage statistics."""
        conn = self._get_connection()
        today = datetime.now().strftime("%Y-%m-%d")

        cursor = conn.execute(
            """SELECT
                COUNT(*) as total_commands,
                SUM(CASE WHEN event_type = 'llm_call' THEN 1 ELSE 0 END) as llm_calls
               FROM usage_events
               WHERE date(timestamp) = ?""",
            (today,)
        )
        row = cursor.fetchone()
        # Note: SQLite SUM() returns NULL when there are no matching rows,
        # so we need to handle None values explicitly
        return {
            "commands_today": row["total_commands"] if row and row["total_commands"] is not None else 0,
            "llm_calls_today": row["llm_calls"] if row and row["llm_calls"] is not None else 0,
        }

    def get_daily_stats(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get daily statistics for the last N days."""
        conn = self._get_connection()
        cursor = conn.execute(
            """SELECT
                date(timestamp) as date,
                COUNT(*) as total_events,
                SUM(CASE WHEN event_type = 'command' THEN 1 ELSE 0 END) as commands,
                SUM(CASE WHEN event_type = 'llm_call' THEN 1 ELSE 0 END) as llm_calls,
                SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful,
                AVG(duration_ms) as avg_duration_ms
               FROM usage_events
               WHERE timestamp >= datetime('now', ?)
               GROUP BY date(timestamp)
               ORDER BY date DESC""",
            (f"-{days} days",)
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_token_stats(self, days: int = 30) -> Dict[str, Any]:
        """Get token usage statistics."""
        conn = self._get_connection()
        cursor = conn.execute(
            """SELECT
                provider,
                model,
                SUM(input_tokens) as total_input,
                SUM(output_tokens) as total_output,
                SUM(cost_estimate) as total_cost,
                COUNT(*) as call_count,
                AVG(latency_ms) as avg_latency
               FROM token_usage
               WHERE timestamp >= datetime('now', ?)
               GROUP BY provider, model
               ORDER BY call_count DESC""",
            (f"-{days} days",)
        )
        return {
            "by_model": [dict(row) for row in cursor.fetchall()],
            "period_days": days,
        }

    def cleanup_old_data(self, retention_days: int = 90) -> int:
        """Remove data older than retention period.

        Returns:
            Number of records deleted
        """
        cutoff = (datetime.now() - timedelta(days=retention_days)).isoformat()
        deleted = 0

        with self._transaction() as cursor:
            cursor.execute("DELETE FROM usage_events WHERE timestamp < ?", (cutoff,))
            deleted += cursor.rowcount

            cursor.execute("DELETE FROM token_usage WHERE timestamp < ?", (cutoff,))
            deleted += cursor.rowcount

        return deleted

    def get_summary(self) -> Dict[str, Any]:
        """Get overall analytics summary."""
        conn = self._get_connection()

        # Total events
        cursor = conn.execute("SELECT COUNT(*) FROM usage_events")
        total_events = cursor.fetchone()[0]

        # Date range
        cursor = conn.execute("SELECT MIN(timestamp), MAX(timestamp) FROM usage_events")
        row = cursor.fetchone()
        date_range = {"from": row[0], "to": row[1]} if row[0] else None

        # Top commands
        cursor = conn.execute(
            """SELECT event_name, COUNT(*) as count
               FROM usage_events
               WHERE event_type = 'command'
               GROUP BY event_name
               ORDER BY count DESC
               LIMIT 5"""
        )
        top_commands = [dict(row) for row in cursor.fetchall()]

        return {
            "total_events": total_events,
            "date_range": date_range,
            "top_commands": top_commands,
        }

