from fastapi import APIRouter, HTTPException, Query

from app.integrations.connections.manager import connection_manager
from app.integrations.google_oauth.schemas import (
    GoogleAuthorizationResponse,
    GoogleConnectionStatus,
)


router = APIRouter(
    prefix="/integrations/google",
    tags=["Google OAuth"],
)


@router.get(
    "/connect",
    response_model=GoogleAuthorizationResponse,
)
async def connect_google(
    user_id: str = Query(..., min_length=1),
):
    try:
        authorization_url = (
            connection_manager.build_authorization_url(
                user_id=user_id,
                provider="google",
            )
        )

        return GoogleAuthorizationResponse(
            authorization_url=authorization_url
        )

    except (RuntimeError, ValueError) as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc


@router.get("/callback")
async def google_callback(
    code: str = Query(...),
    state: str = Query(...),
):
    try:
        user_id = await connection_manager.complete_connection(
            code=code,
            state=state,
            provider="google",
        )

        return {
            "success": True,
            "user_id": user_id,
            "provider": "google",
            "message": "Google account connected successfully",
        }

    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.get(
    "/status",
    response_model=GoogleConnectionStatus,
)
async def google_status(
    user_id: str = Query(..., min_length=1),
):
    return GoogleConnectionStatus(
        connected=connection_manager.status(
            user_id=user_id,
            provider="google",
        )
        == "connected",
        user_id=user_id,
    )


@router.delete("/disconnect")
async def disconnect_google(
    user_id: str = Query(..., min_length=1),
):
    connection_manager.disconnect(
        user_id=user_id,
        provider="google",
    )

    return {
        "success": True,
        "message": "Google account disconnected",
    }