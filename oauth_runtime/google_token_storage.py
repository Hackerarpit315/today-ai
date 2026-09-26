import hashlib
import hmac
import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet


DB_PATH = Path("data/google_oauth.db")


def _get_fernet() -> Fernet:
    key = os.getenv("GOOGLE_TOKEN_ENCRYPTION_KEY", "").strip()

    if not key:
        raise RuntimeError(
            "GOOGLE_TOKEN_ENCRYPTION_KEY is not configured"
        )

    return Fernet(key.encode())


def _get_state_secret() -> bytes:
    secret = os.getenv("GOOGLE_OAUTH_STATE_SECRET", "").strip()

    if not secret:
        raise RuntimeError(
            "GOOGLE_OAUTH_STATE_SECRET is not configured"
        )

    return secret.encode()


def _get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS google_oauth_tokens (
            user_id TEXT PRIMARY KEY,
            encrypted_token TEXT NOT NULL,
            updated_at INTEGER NOT NULL
        )
        """
    )

    connection.commit()

    return connection


def save_token(
    user_id: str,
    token_data: dict[str, Any],
) -> None:
    existing = get_token(user_id)

    token_to_save = dict(token_data)

    if not token_to_save.get("refresh_token") and existing:
        token_to_save["refresh_token"] = existing.get(
            "refresh_token"
        )

    expires_in = token_to_save.get("expires_in")

    if expires_in is not None:
        token_to_save["expires_at"] = int(time.time()) + int(
            expires_in
        )

    encrypted_token = _get_fernet().encrypt(
        json.dumps(token_to_save).encode()
    ).decode()

    connection = _get_connection()

    try:
        connection.execute(
            """
            INSERT INTO google_oauth_tokens
                (user_id, encrypted_token, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id)
            DO UPDATE SET
                encrypted_token = excluded.encrypted_token,
                updated_at = excluded.updated_at
            """,
            (
                user_id,
                encrypted_token,
                int(time.time()),
            ),
        )

        connection.commit()

    finally:
        connection.close()


def get_token(
    user_id: str,
) -> dict[str, Any] | None:
    connection = _get_connection()

    try:
        row = connection.execute(
            """
            SELECT encrypted_token
            FROM google_oauth_tokens
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()

    finally:
        connection.close()

    if row is None:
        return None

    decrypted = _get_fernet().decrypt(
        row["encrypted_token"].encode()
    )

    return json.loads(decrypted.decode())


def delete_token(user_id: str) -> None:
    connection = _get_connection()

    try:
        connection.execute(
            """
            DELETE FROM google_oauth_tokens
            WHERE user_id = ?
            """,
            (user_id,),
        )

        connection.commit()

    finally:
        connection.close()


def create_signed_state(
    user_id: str,
    expires_at: int,
) -> str:
    payload = {
        "user_id": user_id,
        "expires_at": expires_at,
    }

    encoded_payload = json.dumps(
        payload,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()

    signature = hmac.new(
        _get_state_secret(),
        encoded_payload,
        hashlib.sha256,
    ).hexdigest()

    return (
        encoded_payload.hex()
        + "."
        + signature
    )


def verify_signed_state(
    state: str,
) -> dict[str, Any]:
    try:
        payload_hex, signature = state.split(".", 1)

        payload_bytes = bytes.fromhex(payload_hex)

        expected_signature = hmac.new(
            _get_state_secret(),
            payload_bytes,
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(
            signature,
            expected_signature,
        ):
            raise ValueError(
                "Invalid OAuth state signature"
            )

        payload = json.loads(
            payload_bytes.decode()
        )

        if int(payload["expires_at"]) < int(time.time()):
            raise ValueError(
                "OAuth state has expired"
            )

        if not payload.get("user_id"):
            raise ValueError(
                "OAuth state has no user_id"
            )

        return payload

    except (
        ValueError,
        KeyError,
        TypeError,
        json.JSONDecodeError,
    ) as exc:
        raise ValueError(
            "Invalid OAuth state"
        ) from exc