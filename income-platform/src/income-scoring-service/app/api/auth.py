"""
Agent 03 — Income Scoring Service
API: Token issuance endpoint.
"""
import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

router = APIRouter()

_JWT_SECRET = lambda: os.environ["JWT_SECRET"]
_JWT_ALGORITHM = "HS256"


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/auth/token", response_model=TokenResponse, tags=["Auth"])
async def issue_token(form_data: OAuth2PasswordRequestForm = Depends()):
    admin_user = os.environ.get("ADMIN_USERNAME", "admin")
    admin_pass = os.environ.get("ADMIN_PASSWORD", "")
    if not admin_pass:
        raise HTTPException(status_code=503, detail="Auth not configured: ADMIN_PASSWORD not set")
    if form_data.username != admin_user or form_data.password != admin_pass:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {"sub": form_data.username, "iat": now, "exp": now + timedelta(minutes=60)},
        _JWT_SECRET(),
        algorithm=_JWT_ALGORITHM,
    )
    return TokenResponse(access_token=token)
