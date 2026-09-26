from datetime import datetime, timezone
from time import time
from urllib.parse import urlencode

from app.integrations.google_oauth.config import (
    GOOGLE_AUTHORIZATION_URL,
    GOOGLE_CALENDAR_SCOPE,
    GOOGLE_TOKEN_URL,
    OAUTH_STATE_EXPIRY_SECONDS,
    get_google_client_id,
    get_google_client_secret,
    get_google_redirect_uri,
)
from oauth_runtime.google_token_client import exchange_google_code
from oauth_runtime.google_token_refresh import refresh_google_access_token
from oauth_runtime.google_token_storage import (
    create_signed_state,
    delete_token,
    get_token,
    save_token,
    verify_signed_state,
)


class GoogleOAuthService:
    def build_authorization_url(self, user_id: str) -> str:
        expires_at = int(datetime.now(timezone.utc).timestamp()) + (
            OAUTH_STATE_EXPIRY_SECONDS
        )

        state = create_signed_state(
            user_id=user_id,
            expires_at=expires_at,
        )

        params = {
            "client_id": get_google_client_id(),
            "redirect_uri": get_google_redirect_uri(),
            "response_type": "code",
            "scope": GOOGLE_CALENDAR_SCOPE,
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }

        return f"{GOOGLE_AUTHORIZATION_URL}?{urlencode(params)}"

    async def exchange_code(
        self,
        code: str,
        state: str,
    ) -> str:
        state_data = verify_signed_state(state)
        user_id = state_data["user_id"]

        token_data = await exchange_google_code(
            token_url=GOOGLE_TOKEN_URL,
            code=code,
            client_id=get_google_client_id(),
            client_secret=get_google_client_secret(),
            redirect_uri=get_google_redirect_uri(),
        )

        save_token(user_id, token_data)

        return user_id

    async def get_valid_access_token(
        self,
        user_id: str,
    ) -> str:
        token = get_token(user_id)

        if token is None:
            raise RuntimeError("Google account is not connected")

        access_token = token.get("access_token")

        if not access_token:
            raise RuntimeError(
                "Stored Google access token is missing"
            )

        expires_at = token.get("expires_at")

        if expires_at is None:
            return access_token

        if float(expires_at) > time() + 60:
            return access_token

        refresh_token = token.get("refresh_token")

        if not refresh_token:
            raise RuntimeError(
                "Google refresh token is missing"
            )

        refreshed = await refresh_google_access_token(
            token_url=GOOGLE_TOKEN_URL,
            refresh_token=refresh_token,
            client_id=get_google_client_id(),
            client_secret=get_google_client_secret(),
        )

        updated_token = {
            **token,
            **refreshed,
        }

        if "refresh_token" not in refreshed:
            updated_token["refresh_token"] = refresh_token

        save_token(user_id, updated_token)

        return updated_token["access_token"]

    def get_connection_status(self, user_id: str) -> bool:
        return get_token(user_id) is not None

    def get_stored_token(
        self,
        user_id: str,
    ) -> dict | None:
        return get_token(user_id)

    def disconnect(self, user_id: str) -> None:
        delete_token(user_id)


google_oauth_service = GoogleOAuthService()