from typing import Any

from fastapi import APIRouter, Header, HTTPException

from app.integrations.n8n.execution_router import (
    execute_external_action,
)


router = APIRouter(
    prefix="/integrations/n8n",
    tags=["n8n Execution"],
)


@router.post("/execute")
async def execute_n8n_action(
    payload: dict[str, Any],
    x_today_ai_user_id: str = Header(...),
):
    user_id = x_today_ai_user_id.strip()

    if not user_id:
        raise HTTPException(
            status_code=400,
            detail="Today AI user ID is required",
        )

    action = payload.get("action")

    if not isinstance(action, dict):
        raise HTTPException(
            status_code=400,
            detail="Request requires an action object",
        )

    try:
        return await execute_external_action(
            user_id=user_id,
            action=action,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="External action execution failed",
        ) from exc