# Authentication Guide

All Income Fortress API endpoints (except `/health`) require JWT Bearer token authentication.

## Token Format

Tokens use **HS256** (HMAC with SHA-256) and follow the standard JWT structure:

```
<header>.<payload>.<signature>
```

Example token (split for readability):

```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.
eyJzdWIiOiJ1c2VyLTEyMyIsImV4cCI6MTc0NjEyMzQ1Nn0.
aBcD_ef-GhI1jKlMnOpQrSt_UvWxYzAb-CdEfGhIjKl
```

## Token Transmission

Include the token in every request using the `Authorization` header:

```
Authorization: Bearer <token>
```

### Example cURL Request

```bash
curl -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  http://localhost:8001/stocks/AAPL/price
```

### Example Python Request

```python
import requests

token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
headers = {"Authorization": f"Bearer {token}"}
response = requests.get("http://localhost:8001/stocks/AAPL/price", headers=headers)
print(response.json())
```

## Token Generation

### Using Python (No Dependencies)

Generate a JWT token using only the Python standard library:

```python
import base64
import hashlib
import hmac
import json
import time

def generate_token(secret: str, user_id: str, expires_in_seconds: int = 3600) -> str:
    """
    Generate a JWT token with HS256 signature.

    Args:
        secret: JWT_SECRET from environment
        user_id: Identifier for the token subject (e.g., "user-123")
        expires_in_seconds: Token lifetime in seconds (default 1 hour)

    Returns:
        Complete JWT token string
    """
    # Header
    header = {"alg": "HS256", "typ": "JWT"}
    header_encoded = base64.urlsafe_b64encode(
        json.dumps(header).encode()
    ).rstrip(b"=").decode()

    # Payload
    now = int(time.time())
    payload = {
        "sub": user_id,
        "exp": now + expires_in_seconds,
        "iat": now,
    }
    payload_encoded = base64.urlsafe_b64encode(
        json.dumps(payload).encode()
    ).rstrip(b"=").decode()

    # Signature
    message = f"{header_encoded}.{payload_encoded}".encode()
    signature = base64.urlsafe_b64encode(
        hmac.new(secret.encode(), message, hashlib.sha256).digest()
    ).rstrip(b"=").decode()

    return f"{header_encoded}.{payload_encoded}.{signature}"


# Generate a token
secret = "your-jwt-secret"
token = generate_token(secret, "user-123", expires_in_seconds=3600)
print(f"Token: {token}")
```

### Using PyJWT (Alternative)

If you have the `pyjwt` library available:

```python
import jwt
import time

secret = "your-jwt-secret"
payload = {
    "sub": "user-123",
    "exp": int(time.time()) + 3600,
}
token = jwt.encode(payload, secret, algorithm="HS256")
print(f"Token: {token}")
```

## Token Validation

All services validate tokens on receipt:

1. **Signature verification**: Uses `JWT_SECRET` to verify the HMAC-SHA256 signature
2. **Expiry check**: Ensures the `exp` claim timestamp is in the future
3. **Structure validation**: Ensures the token has exactly 3 parts (header.payload.signature)

If validation fails, the service returns:

```json
{
  "detail": "Invalid or expired token"
}
```

## HTTP Status Codes for Auth Failures

| Code | Reason | Solution |
|------|--------|----------|
| 401 | Missing token, malformed token, or invalid signature | Ensure `Authorization: Bearer <token>` header is present and token is valid |
| 401 | Token expired | Generate a new token with updated `exp` claim |
| 403 | Token valid but endpoint requires higher permissions | Use a token with appropriate permissions (future extension) |

## Token Expiry Handling

Tokens include an `exp` (expiration) claim representing the Unix timestamp when the token becomes invalid.

### When a Token Expires

- **Before expiry**: ✓ Token is accepted
- **After expiry**: ✗ Request rejected with 401 status
- **Close to expiry**: No warning is issued; clients must handle token refresh

### Best Practices

1. **Request new tokens before expiry** — typical tokens expire in 1 hour; refresh after 50 minutes
2. **Store securely** — treat tokens like passwords; never log them
3. **Use HTTPS** — always transmit tokens over encrypted connections
4. **Short expiry times** — keep `expires_in_seconds` as low as practical (default 1 hour)

### Token Refresh Flow

Since tokens cannot be renewed, the typical flow is:

1. User/service calls auth system to get a new token
2. Old token is discarded
3. New token is used for subsequent API calls

The Income Fortress platform assumes an external auth service (not documented here) issues and rotates tokens.

## Secret Management

The `JWT_SECRET` environment variable must be:

- **Strong**: Minimum 32 characters, cryptographically random
- **Unique**: Different value per environment (dev, staging, prod)
- **Secure**: Never logged, never committed to version control
- **Rotated**: Changed periodically (e.g., annually or after compromise)

### Setting the Secret

**In `.env` (development only):**

```bash
JWT_SECRET=your-32-character-minimum-random-secret-here
```

**In production:**

Use your deployment system's secret management (e.g., Kubernetes Secrets, AWS Secrets Manager, HashiCorp Vault).

## Health Endpoints (No Auth)

The `/health` endpoint on each service does not require authentication:

```bash
curl http://localhost:8001/health
```

This allows load balancers and monitoring systems to check service status without token management.

## Troubleshooting Auth Errors

### "Invalid or expired token"

**Possible causes:**
- Token signature is invalid (wrong secret used to sign)
- Token has expired (check `exp` claim timestamp)
- Token format is malformed (missing dot separator)

**Solution:**
```bash
# Regenerate token with correct secret
python generate_token.py

# Verify token structure online at https://jwt.io (be cautious with sensitive secrets)
```

### "Missing authorization header"

**Cause:** Request missing the `Authorization: Bearer ...` header

**Solution:**
```bash
# Always include Authorization header:
curl -H "Authorization: Bearer $TOKEN" http://localhost:8001/stocks/AAPL/price
```

### Token Works on One Service But Not Another

**Cause:** Each service may have a different `JWT_SECRET` configured

**Solution:**
- Verify all services are using the **same JWT_SECRET** environment variable
- In production, use a shared secret management system

## Future: OAuth 2.0 / OIDC

Current authentication is JWT-based without OAuth 2.0 or OIDC. If integrating with SSO systems in the future:

- Tokens will still be JWTs
- Issuance may shift to an OAuth provider
- Token validation remains the same

No changes needed to client code unless the token format changes.
