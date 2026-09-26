from pydantic import BaseModel


class GoogleAuthorizationResponse(BaseModel):
    authorization_url: str


class GoogleConnectionStatus(BaseModel):
    connected: bool
    user_id: str


class GoogleTokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    scope: str | None = None
    