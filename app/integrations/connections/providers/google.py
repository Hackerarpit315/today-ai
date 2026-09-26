from typing import Any

from app.integrations.google_oauth.service import google_oauth_service


class GoogleConnectionProvider:
    provider = "google"

    def build_authorization_url(
        self,
        user_id: str,
    ) -> str:
        return google_oauth_service.build_authorization_url(
            user_id=user_id,
        )

    async def complete_connection(
        self,
        code: str,
        state: str,
    ) -> str:
        return await google_oauth_service.exchange_code(
            code=code,
            state=state,
        )

    def is_connected(
        self,
        user_id: str,
    ) -> bool:
        return google_oauth_service.get_connection_status(
            user_id=user_id,
        )

    def disconnect(
        self,
        user_id: str,
    ) -> None:
        google_oauth_service.disconnect(
            user_id=user_id,
        )


google_connection_provider = GoogleConnectionProvider()