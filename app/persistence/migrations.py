from __future__ import annotations

import importlib

sqlite3 = importlib.import_module("sqlite3")


SCHEMA_VERSION = 1


def apply_migrations(connection: sqlite3.Connection) -> None:
    """Apply all known schema migrations; safe to run repeatedly."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY
        )
        """
    )

    current = connection.execute(
        "SELECT COALESCE(MAX(version), 0) AS version FROM schema_migrations"
    ).fetchone()["version"]

    if current < 1:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS memories (
                memory_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                memory_type TEXT NOT NULL,
                key TEXT NOT NULL,
                value_json TEXT NOT NULL,
                importance TEXT NOT NULL,
                sensitivity TEXT NOT NULL,
                status TEXT NOT NULL,
                source TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                expires_at TEXT,
                version INTEGER NOT NULL CHECK (version >= 1)
            );

            CREATE INDEX IF NOT EXISTS idx_memories_user_id
                ON memories(user_id);

            CREATE INDEX IF NOT EXISTS idx_memories_active_key
                ON memories(user_id, memory_type, key, status);

            CREATE TABLE IF NOT EXISTS audit_events (
                event_id TEXT PRIMARY KEY,
                request_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                module TEXT NOT NULL,
                event_type TEXT NOT NULL,
                status TEXT NOT NULL,
                severity TEXT NOT NULL,
                actor TEXT NOT NULL,
                action_id TEXT,
                resource_type TEXT,
                resource_id TEXT,
                message TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                correlation_id TEXT NOT NULL,
                parent_event_id TEXT,
                user_id TEXT,
                error_code TEXT,
                reason TEXT,
                duration_ms INTEGER,
                ip_hash TEXT,
                policy_version TEXT,
                integrity_hash TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_audit_timestamp
                ON audit_events(timestamp, event_id);

            CREATE INDEX IF NOT EXISTS idx_audit_request_id
                ON audit_events(request_id);

            CREATE INDEX IF NOT EXISTS idx_audit_user_id
                ON audit_events(user_id);

            INSERT INTO schema_migrations(version) VALUES (1);
            """
        )

    connection.commit()
