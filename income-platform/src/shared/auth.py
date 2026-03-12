"""
income-platform — shared JWT authentication dependency.
Used by all FastAPI services via Depends(verify_token).
"""
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

_bearer = HTTPBearer(auto_error=True)

JWT_ALGORITHM = "HS256"
JWT_SECRET_ENV = "JWT_SECRET"


def _get_secret() -> str:
    secret = os.environ.get(JWT_SECRET_ENV)
    if not secret:
        raise RuntimeError(f"{JWT_SECRET_ENV} environment variable is not set")
    return secret


def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict:
    """FastAPI dependency — validates Bearer JWT. Raises 401 on failure."""
    try:
        payload = jwt.decode(
            credentials.credentials,
            _get_secret(),
            algorithms=[JWT_ALGORITHM],
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def create_access_token(subject: str, expires_minutes: int = 60) -> str:
    """Create a signed JWT. Used by the /auth/token endpoint."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes),
    }
    return jwt.encode(payload, _get_secret(), algorithm=JWT_ALGORITHM)


def create_service_token(subject: str = "service") -> str:
    """Create a long-lived service-to-service token (30 days)."""
    return create_access_token(subject=subject, expires_minutes=43200)
