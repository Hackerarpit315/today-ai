"""Request identifiers."""

from uuid import uuid4


def new_request_id() -> str:
    """Return a new UUID4 string (CSPRNG via os.urandom)."""
    return str(uuid4())
