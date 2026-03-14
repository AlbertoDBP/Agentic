"""JWT generation for service-to-service calls."""
import time

import jwt

from app.config import settings


def make_token() -> str:
    now = int(time.time())
    return jwt.encode(
        {"sub": "admin-panel", "iat": now, "exp": now + 300},
        settings.jwt_secret,
        algorithm="HS256",
    )


def auth_headers() -> dict:
    return {
        "Authorization": f"Bearer {make_token()}",
        "Content-Type": "application/json",
    }
