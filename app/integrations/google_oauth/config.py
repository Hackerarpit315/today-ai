import os


GOOGLE_AUTHORIZATION_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"

GOOGLE_CALENDAR_SCOPE = (
    "https://www.googleapis.com/auth/calendar.events.owned"
)


def get_google_client_id() -> str:
    value = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "").strip()
    if not value:
        raise RuntimeError("GOOGLE_OAUTH_CLIENT_ID is not configured")
    return value


def get_google_client_secret() -> str:
    value = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "").strip()
    if not value:
        raise RuntimeError("GOOGLE_OAUTH_CLIENT_SECRET is not configured")
    return value


def get_google_redirect_uri() -> str:
    value = os.getenv("GOOGLE_OAUTH_REDIRECT_URI", "").strip()
    if not value:
        raise RuntimeError("GOOGLE_OAUTH_REDIRECT_URI is not configured")
    return value


def get_oauth_state_secret() -> str:
    value = os.getenv("GOOGLE_OAUTH_STATE_SECRET", "").strip()
    if not value:
        raise RuntimeError("GOOGLE_OAUTH_STATE_SECRET is not configured")
    return value


def get_token_encryption_key() -> str:
    value = os.getenv("GOOGLE_TOKEN_ENCRYPTION_KEY", "").strip()
    if not value:
        raise RuntimeError("GOOGLE_TOKEN_ENCRYPTION_KEY is not configured")
    return value


OAUTH_STATE_EXPIRY_SECONDS = 600