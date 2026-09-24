# Database + Persistence Integration

## Purpose

Today AI can persist M12 Memory and M13 Audit data in a local SQLite database without changing the public module contracts.

The existing in-memory repositories remain available and remain the default when services are created without an explicit repository.

## Architecture

```text
Service
   ↓
Repository contract
   ↓
SQLite repository
   ↓
SQLite
```

Persistence is explicit. The application does not create a database merely because the persistence modules are imported.

## Database

Technology: Python standard-library `sqlite3`.

Configuration:

```text
TODAY_AI_DB_PATH
```

If unset, the default is:

```text
data/today_ai.db
```

The database directory is created when explicit database initialization or a SQLite repository is constructed.

Database initialization:

```python
from app.persistence.database import initialize_database

initialize_database()
```

Initialization is idempotent and uses schema migration version `1`.

The generated database files are ignored by Git.

## M12 Memory

`SQLiteMemoryRepository` implements the same `get`, `save`, and `all` repository behavior used by `MemoryService`.

It preserves:

- UUID memory IDs
- user isolation
- memory type/key
- value
- importance and sensitivity
- status
- source
- timestamps
- expiry
- versioning
- deterministic retrieval/list behavior
- M12 forget semantics

Memory values are stored as JSON. Non-JSON values are rejected rather than silently discarded.

The existing `InMemoryMemoryRepository` remains available for tests and lightweight operation.

Example:

```python
from app.services.memory_service import MemoryService
from app.persistence.repositories.memory_repository import SQLiteMemoryRepository

service = MemoryService(SQLiteMemoryRepository())
```

## M13 Audit

`SQLiteAuditRepository` implements the existing audit repository contract.

It preserves:

- immutable audit events at the application repository level
- append-only create behavior
- retrieval
- filtering
- searching
- pagination
- deterministic ordering
- existing service-level secret rejection
- integrity hashes and verification

There are no update/delete methods in the audit repository.

Example:

```python
from app.services.audit_service import AuditService
from app.persistence.repositories.audit_repository import SQLiteAuditRepository

service = AuditService(SQLiteAuditRepository())
```

## Security

- SQL statements use parameterized values.
- No generic SQL execution endpoint exists.
- No database administration API was added.
- No credentials or API keys are stored.
- M12/M13 service-level secret checks remain active.
- Database errors are not silently swallowed by persistence repositories.
- Database paths are not exposed by an API error handler.
- No external network service is used.
- No authentication or CORS behavior was added.

## Tests

New persistence tests use temporary SQLite database files and clean up through pytest's temporary directory handling.

The persistence test suite covers initialization, configuration, memory CRUD/forget behavior, persistence across repository instances, expiry, user isolation, audit append/retrieval/filter/search/pagination, immutability, integrity verification, parameterized SQL, invalid database handling, in-memory repository compatibility, Assistant API regression, network restrictions, and secret-storage protection.

Verified results in the implementation environment:

```text
27 passed
674 passed
```

The full suite includes the 27 new persistence tests.

## Limitations

- SQLite is intended for local single-application persistence in this phase.
- No multi-process deployment strategy or database server was introduced.
- Existing APIs/services do not silently switch from in-memory to SQLite; callers explicitly choose the repository.
- No frontend, LLM, n8n, external actions, or external APIs are part of this phase.
