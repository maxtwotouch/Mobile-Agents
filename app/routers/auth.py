import os

from fastapi import APIRouter, HTTPException

from app.auth import (
    TokenRequest,
    TokenResponse,
    check_password,
    create_token,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/status")
async def auth_status():
    """Check if auth is disabled (for frontend to skip login screen)."""
    return {"auth_disabled": os.environ.get("MA_AUTH_DISABLED") == "1"}


@router.post("/login", response_model=TokenResponse)
async def login(body: TokenRequest):
    if not check_password(body.username, body.password):
        raise HTTPException(401, "Invalid credentials")

    token, expires = create_token(body.username)
    return TokenResponse(
        access_token=token,
        expires_at=expires.isoformat(),
    )
