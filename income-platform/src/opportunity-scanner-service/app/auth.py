"""JWT verification dependency for this service."""
import os
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

_bearer = HTTPBearer(auto_error=True)
_ALGORITHM = "HS256"


def create_access_token(data: dict) -> str:
    """Encode a JWT token for the given payload. Uses JWT_SECRET from environment."""
    secret = os.environ.get("JWT_SECRET", "test-secret")
    return jwt.encode(data, secret, algorithm=_ALGORITHM)


def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict:
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        raise HTTPException(status_code=503, detail="JWT_SECRET not configured")
    try:
        return jwt.decode(credentials.credentials, secret, algorithms=[_ALGORITHM])
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
