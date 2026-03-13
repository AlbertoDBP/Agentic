"""JWT verification dependency — HS256 HTTPBearer."""
import os
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

_bearer = HTTPBearer(auto_error=True)
_ALGORITHM = "HS256"

# Callers accepted: Agent 08, Agent 12, and generic service tokens.
_ALLOWED_SUBJECTS = {"agent-08", "agent-12", "service"}


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(_bearer)) -> dict:
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        raise HTTPException(status_code=503, detail="JWT_SECRET not configured")
    try:
        payload = jwt.decode(credentials.credentials, secret, algorithms=[_ALGORITHM])
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
