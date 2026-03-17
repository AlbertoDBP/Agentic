"""Broker Service — JWT authentication (same pattern as all platform services)."""
import os

import jwt
from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

_security = HTTPBearer()
_JWT_SECRET = os.environ.get("JWT_SECRET", "")


def verify_token(credentials: HTTPAuthorizationCredentials = Security(_security)):
    try:
        jwt.decode(credentials.credentials, _JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired",
                            headers={"WWW-Authenticate": "Bearer"})
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token",
                            headers={"WWW-Authenticate": "Bearer"})
    return credentials.credentials
