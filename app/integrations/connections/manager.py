from typing import Any

from app.integrations.connections.models import (
    Connection,
    ConnectionStatus,
)
from app.integrations.connections.store import connection_store
from app.integrations.connections.providers.google import (
    google_connection_provider,
)


class ConnectionManager:
    def __init__(self) -> None:
        self._providers = {
            google_connection_provider.provider: google_connection_provider,
        }

    def get_provider(self, provider: str):
        provider = provider.strip().lower()

        selected_provider = self._providers.get(provider)

        if selected_provider is None:
            raise ValueError(
                f"Unsupported connection provider: {provider}"
            )

        return selected_provider

    def build_authorization_url(
        self,
        user_id: str,
        provider: str,
    ) -> str:
        user_id = user_id.strip()
        provider = provider.strip().lower()

        if not user_id:
            raise ValueError("user_id is required")

        selected_provider = self.get_provider(provider)

        return selected_provider.build_authorization_url(
            user_id=user_id,
        )

    async def complete_connection(
        self,
        code: str,
        state: str,
        provider: str,
    ) -> str:
        provider = provider.strip().lower()

        selected_provider = self.get_provider(provider)

        user_id = await selected_provider.complete_connection(
            code=code,
            state=state,
        )

        connection = connection_store.get(
            user_id=user_id,
            provider=provider,
        )

        if connection is None:
            connection = Connection(
                user_id=user_id,
                provider=provider,
            )

        connection.mark_connected()

        connection_store.save(connection)

        return user_id

    def connect(
        self,
        user_id: str,
        provider: str,
        services: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Connection:
        user_id = user_id.strip()
        provider = provider.strip().lower()

        if not user_id:
            raise ValueError("user_id is required")

        self.get_provider(provider)

        connection = connection_store.get(
            user_id=user_id,
            provider=provider,
        )

        if connection is None:
            connection = Connection(
                user_id=user_id,
                provider=provider,
            )

        connection.mark_connected(
            services=services,
            metadata=metadata,
        )

        connection_store.save(connection)

        return connection

    def get(
        self,
        user_id: str,
        provider: str,
    ) -> Connection | None:
        return connection_store.get(
            user_id=user_id,
            provider=provider.strip().lower(),
        )

    def status(
        self,
        user_id: str,
        provider: str,
    ) -> ConnectionStatus:
        provider = provider.strip().lower()

        connection = self.get(
            user_id=user_id,
            provider=provider,
        )

        if connection is not None:
            return connection.status

        selected_provider = self.get_provider(provider)

        if selected_provider.is_connected(user_id):
            return ConnectionStatus.CONNECTED

        return ConnectionStatus.DISCONNECTED

    def list_connections(
        self,
        user_id: str,
    ) -> list[Connection]:
        return connection_store.list_for_user(
            user_id=user_id,
        )

    def disconnect(
        self,
        user_id: str,
        provider: str,
    ) -> bool:
        provider = provider.strip().lower()

        selected_provider = self.get_provider(provider)

        selected_provider.disconnect(user_id)

        connection = self.get(
            user_id=user_id,
            provider=provider,
        )

        if connection is None:
            return True

        connection.mark_disconnected()
        connection_store.save(connection)

        return True

    def remove(
        self,
        user_id: str,
        provider: str,
    ) -> bool:
        return connection_store.delete(
            user_id=user_id,
            provider=provider.strip().lower(),
        )


connection_manager = ConnectionManager()