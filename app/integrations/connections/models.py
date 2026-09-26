from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class ConnectionStatus(str, Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"


@dataclass
class Connection:
    user_id: str
    provider: str
    services: list[str] = field(default_factory=list)
    status: ConnectionStatus = ConnectionStatus.DISCONNECTED
    connected_at: datetime | None = None
    updated_at: datetime | None = None
    metadata: dict = field(default_factory=dict)

    def mark_connected(
        self,
        services: list[str] | None = None,
        metadata: dict | None = None,
    ) -> None:
        now = datetime.now(timezone.utc)

        self.status = ConnectionStatus.CONNECTED
        self.connected_at = self.connected_at or now
        self.updated_at = now

        if services is not None:
            self.services = list(services)

        if metadata is not None:
            self.metadata = dict(metadata)

    def mark_disconnected(self) -> None:
        self.status = ConnectionStatus.DISCONNECTED
        self.updated_at = datetime.now(timezone.utc)

    def mark_error(self, metadata: dict | None = None) -> None:
        self.status = ConnectionStatus.ERROR
        self.updated_at = datetime.now(timezone.utc)

        if metadata is not None:
            self.metadata = dict(metadata)