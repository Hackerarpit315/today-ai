from __future__ import annotations

import os

from app.persistence.repositories.audit_repository import SQLiteAuditRepository
from app.persistence.repositories.memory_repository import SQLiteMemoryRepository
from app.services.audit_service import AuditService
from app.services.memory_service import MemoryService


PERSISTENCE_ENV_VAR = "TODAY_AI_PERSISTENCE"
SQLITE_MODE = "sqlite"


def sqlite_persistence_enabled() -> bool:
    """Return whether application services should use SQLite repositories.

    SQLite is enabled explicitly with TODAY_AI_PERSISTENCE=sqlite.  A configured
    TODAY_AI_DB_PATH also enables SQLite so the existing database-path setting
    remains sufficient for local application activation.
    """
    mode = os.environ.get(PERSISTENCE_ENV_VAR, "").strip().lower()
    return mode == SQLITE_MODE or bool(os.environ.get("TODAY_AI_DB_PATH"))


def create_memory_service() -> MemoryService:
    """Create a memory service with the configured repository backend."""
    if sqlite_persistence_enabled():
        return MemoryService(SQLiteMemoryRepository())
    return MemoryService()


def create_audit_service() -> AuditService:
    """Create an audit service with the configured repository backend."""
    if sqlite_persistence_enabled():
        return AuditService(SQLiteAuditRepository())
    return AuditService()
