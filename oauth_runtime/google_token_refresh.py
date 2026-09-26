from typing import Any

import httpx


async def refresh_google_access_token(
    token_url: str,
    refresh_token: str,
    client_id: str,
    client_secret: str,
) -> dict[str, Any]:
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            token_url,
            data=payload,
        )

    response.raise_for_status()

    token_data = response.json()

    if "access_token" not in token_data:
        raise RuntimeError(
            "Google refresh response did not contain an access_token"
        )

    return token_data
