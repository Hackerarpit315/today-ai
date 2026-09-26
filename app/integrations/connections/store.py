from threading import Lock

from app.integrations.connections.models import Connection


class ConnectionStore:
    def __init__(self) -> None:
        self._connections: dict[tuple[str, str], Connection] = {}
        self._lock = Lock()

    def save(self, connection: Connection) -> Connection:
        key = (connection.user_id, connection.provider)

        with self._lock:
            self._connections[key] = connection

        return connection

    def get(
        self,
        user_id: str,
        provider: str,
    ) -> Connection | None:
        key = (user_id, provider)

        with self._lock:
            return self._connections.get(key)

    def list_for_user(
        self,
        user_id: str,
    ) -> list[Connection]:
        with self._lock:
            return [
                connection
                for connection in self._connections.values()
                if connection.user_id == user_id
            ]

    def delete(
        self,
        user_id: str,
        provider: str,
    ) -> bool:
        key = (user_id, provider)

        with self._lock:
            if key not in self._connections:
                return False

            del self._connections[key]
            return True

    def clear(self) -> None:
        with self._lock:
            self._connections.clear()


connection_store = ConnectionStore()