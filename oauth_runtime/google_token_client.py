from typing import Any

import httpx


async def exchange_google_code(
    token_url: str,
    code: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
) -> dict[str, Any]:
    payload = {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
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
            "Google token response did not contain an access_token"
        )

    return token_data