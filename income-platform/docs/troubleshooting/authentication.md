# Authentication Errors

Troubleshooting JWT tokens and authorization issues.

---

## Error: 401 Unauthorized: Invalid token

**Symptom:** Protected endpoint returns:
```
HTTP 401
{"detail": "Invalid token"}
```

**Root Cause:** JWT token signature verification failed. Token was signed with different secret or corrupted.

**Immediate Fix:**

1. Verify JWT_SECRET is same everywhere:
```bash
# Check in .env
grep JWT_SECRET .env

# Check in container
docker compose exec market-data-service python3 -c "import os; print(os.environ.get('JWT_SECRET'))"
```

2. Regenerate token with correct secret:
```bash
python3 -c "
import base64, hashlib, hmac, json, time

secret = 'your-jwt-secret'
header = base64.urlsafe_b64encode(json.dumps({'alg': 'HS256', 'typ': 'JWT'}).encode()).rstrip(b'=').decode()
payload = base64.urlsafe_b64encode(json.dumps({'sub': 'test', 'exp': int(time.time()) + 3600}).encode()).rstrip(b'=').decode()
sig = base64.urlsafe_b64encode(hmac.new(secret.encode(), f'{header}.{payload}'.encode(), hashlib.sha256).digest()).rstrip(b'=').decode()
print(f'{header}.{payload}.{sig}')
"
```

3. Test with new token:
```bash
TOKEN='new-token-here'
curl -H "Authorization: Bearer $TOKEN" http://localhost:8001/health
```

**Prevention:**
- JWT_SECRET should be same in all services
- Store in `.env` at repo root and reference from each service
- Generate strong secret: `openssl rand -hex 32`
- Don't change JWT_SECRET mid-deployment without invalidating old tokens

---

## Error: 401 Unauthorized: Invalid token (wrong algorithm)

**Symptom:** 401 with "Invalid token" but token looks valid (3 dot-separated segments).

**Root Cause:** Token created with different algorithm (e.g., HS512) but service expects HS256.

**Immediate Fix:**

Check the token header:
```bash
TOKEN='your-token'
python3 -c "
import base64, json
header = json.loads(base64.urlsafe_b64decode('$TOKEN'.split('.')[0] + '==='))
print(f'Algorithm: {header.get(\"alg\")}')
"
```

Must be `HS256`. If not, regenerate with correct algorithm.

**Prevention:**
- Always use HS256 for JWT tokens
- Document the algorithm in auth.py comments (already done)
- Test token generation in test suite

---

## Error: 401 Unauthorized: Token has expired

**Symptom:** Protected endpoint returns:
```
HTTP 401
{"detail": "Token has expired"}
```

**Root Cause:** Token `exp` (expiration) claim is in the past.

**Immediate Fix:**

Generate new token with future expiration:
```bash
python3 -c "
import base64, hashlib, hmac, json, time

secret = 'your-jwt-secret'
exp_time = int(time.time()) + 3600  # 1 hour from now
header = base64.urlsafe_b64encode(json.dumps({'alg': 'HS256', 'typ': 'JWT'}).encode()).rstrip(b'=').decode()
payload = base64.urlsafe_b64encode(json.dumps({'sub': 'test', 'exp': exp_time}).encode()).rstrip(b'=').decode()
sig = base64.urlsafe_b64encode(hmac.new(secret.encode(), f'{header}.{payload}'.encode(), hashlib.sha256).digest()).rstrip(b'=').decode()
print(f'{header}.{payload}.{sig}')
"
```

**Prevention:**
- Set token expiration to reasonable value (1 hour for API, longer for refresh tokens)
- Check token expiration before using: `exp > time.time()`
- Implement token refresh mechanism for long-lived sessions
- Log token generation/expiration in audit trail

---

## Error: 403 Forbidden: Missing auth header

**Symptom:** Protected endpoint returns:
```
HTTP 403
{"detail": "Invalid credentials"}
```

When calling without `Authorization` header.

**Root Cause:** No `Authorization: Bearer <token>` header provided.

**Immediate Fix:**

Add Authorization header to request:
```bash
TOKEN='your-jwt-token'
curl -H "Authorization: Bearer $TOKEN" http://localhost:8001/stocks/AAPL/price
```

With curl:
```bash
curl -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     http://localhost:8001/api/endpoint
```

With Python requests:
```python
import requests

token = 'your-jwt-token'
headers = {'Authorization': f'Bearer {token}'}
response = requests.get('http://localhost:8001/stocks/AAPL/price', headers=headers)
```

With JavaScript fetch:
```javascript
const token = 'your-jwt-token';
const response = await fetch('http://localhost:8001/stocks/AAPL/price', {
  headers: {
    'Authorization': `Bearer ${token}`
  }
});
```

**Prevention:**
- Always include `Authorization` header for protected endpoints
- Document required headers in API docs (already in `/docs`)
- Test with and without auth in test suite

---

## Error: 503 Service Unavailable: JWT_SECRET not configured

**Symptom:** Any endpoint returns:
```
HTTP 503
{"detail": "JWT_SECRET not configured"}
```

**Root Cause:** JWT_SECRET environment variable not set or empty when `verify_token()` is called.

**Immediate Fix:**

1. Set JWT_SECRET in `.env`:
```bash
echo "JWT_SECRET=$(openssl rand -hex 32)" >> .env
```

2. Or in docker-compose.yml:
```yaml
environment:
  - JWT_SECRET=your-secret-here
```

3. Restart services:
```bash
docker compose down
docker compose up -d
```

4. Verify it's set:
```bash
docker compose exec market-data-service python3 -c "import os; print('JWT_SECRET set' if os.environ.get('JWT_SECRET') else 'NOT SET')"
```

**Prevention:**
- `.env` file must exist in repo root
- CI/CD must inject JWT_SECRET before deployment
- Fail at startup (not first request): validate env vars in config.py
- Use pydantic-settings to enforce required variables

---

## Error: Invalid token format / Token has invalid claims

**Symptom:** Token verification fails with:
```
json.JSONDecodeError: Expecting value
```

Or:
```
base64 padding error
```

**Root Cause:** Token format is invalid (not 3 dot-separated base64url segments).

**Immediate Fix:**

Validate token format:
```python
def validate_token_format(token: str) -> bool:
    parts = token.split('.')
    if len(parts) != 3:
        return False
    # Each part should be valid base64url
    for part in parts:
        try:
            padding = 4 - len(part) % 4
            base64.urlsafe_b64decode(part + '=' * padding)
        except:
            return False
    return True

token = 'your-token'
print('Valid' if validate_token_format(token) else 'Invalid')
```

**Prevention:**
- Use token generation helper in conftest.py (already provided)
- Always validate token structure before verification
- Use JWT libraries for generation (though stdlib-only is used here)

---

## Error: Module auth not found / ImportError on startup

**Symptom:** Container exits with:
```
ImportError: cannot import name 'verify_token' from 'auth'
ModuleNotFoundError: No module named 'auth'
```

**Root Cause:** JWT_SECRET not set BEFORE app modules imported. Auth module is imported during app initialization.

**Immediate Fix:**

In test code, set JWT_SECRET first:
```python
import os
os.environ['JWT_SECRET'] = 'test-secret'  # SET THIS FIRST

# Now safe to import app
from main import app
```

This is already correctly done in `conftest.py` at the very top.

For containers, ensure JWT_SECRET is in `.env` before `docker compose up`:
```bash
# In .env
JWT_SECRET=your-secret

# Then start
docker compose up -d
```

**Prevention:**
- conftest.py must set JWT_SECRET at module import time (not in fixtures)
- Use `pytest` not `python -m pytest` directly on test files
- Document the import ordering requirement in conftest.py

---

## Error: Token validation passes but claims missing

**Symptom:** Request succeeds but payload is empty:
```json
{}
```

**Root Cause:** Token verified but claims weren't properly extracted from payload.

**Immediate Fix:**

Verify token has required claims:
```python
python3 -c "
import base64, json, time

token = 'your-token'
payload_b64 = token.split('.')[1]
padding = 4 - len(payload_b64) % 4
payload = json.loads(base64.urlsafe_b64decode(payload_b64 + '=' * padding))
print(f'Payload: {payload}')
print(f'Has sub claim: {\"sub\" in payload}')
print(f'Has exp claim: {\"exp\" in payload}')
print(f'Expired: {payload.get(\"exp\", 0) < time.time()}')
"
```

Add required claims when generating:
```python
payload = {
    'sub': 'user_id',
    'exp': int(time.time()) + 3600,
    'iat': int(time.time()),
}
```

**Prevention:**
- Include standard claims: `sub`, `exp`, `iat`
- Document required claims in auth.py
- Validate claims in verify_token() (already done for `exp`)

---

## Error: CORS blocked auth request

**Symptom:** Browser console shows:
```
Access to XMLHttpRequest blocked by CORS policy
```

When calling protected endpoints from browser.

**Root Cause:** CORS not configured to allow Authorization header.

**Immediate Fix:**

Enable CORS for Authorization header in FastAPI:
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],  # Includes Authorization
)
```

This is already configured in income-scoring service, but may need to be added to other services.

**Prevention:**
- Always include `allow_headers=["*"]` or explicitly list Authorization
- Test from browser before production
- Use `/docs` FastAPI UI to test CORS requests

---

## Error: 401 with Bearer token missing from header

**Symptom:** Endpoint returns 401 even though header was included:
```bash
curl -H "Authorization: Bearer token" http://localhost:8001/api
```

**Root Cause:** Authorization header format wrong. Must be exactly `Authorization: Bearer <token>`.

**Immediate Fix:**

Check exact header format:
```bash
TOKEN='your-token'

# Correct
curl -H "Authorization: Bearer $TOKEN" http://localhost:8001/health

# Wrong (missing Bearer)
# curl -H "Authorization: $TOKEN" http://localhost:8001/health

# Wrong (different keyword)
# curl -H "Authorization: JWT $TOKEN" http://localhost:8001/health
```

**Prevention:**
- Documentation must show exact header format
- Test with curl before building client
- Log received headers in debug mode: `log_level: DEBUG`

---

## Test Configuration: JWT_SECRET Ordering

**Issue:** Tests fail with auth import error.

**Solution:** conftest.py sets JWT_SECRET BEFORE importing app:

```python
# conftest.py - THIS MUST BE FIRST
import os
os.environ.setdefault("JWT_SECRET", "test-secret")

# ... only then import app modules
from main import app
```

Never do:
```python
# WRONG - app imports before JWT_SECRET is set
from main import app

@pytest.fixture
def set_jwt_secret():
    os.environ['JWT_SECRET'] = 'test-secret'  # Too late!
```

---

## Debugging Checklist

- [ ] Authorization header present? `curl -H "Authorization: Bearer <token>" ...`
- [ ] Token format valid? 3 dot-separated base64url segments?
- [ ] JWT_SECRET set in container? `docker compose exec market-data-service env | grep JWT_SECRET`
- [ ] JWT_SECRET same in all services? `grep JWT_SECRET docker-compose.yml .env`
- [ ] Token not expired? Check `exp` claim timestamp
- [ ] Algorithm correct? Token header should have `"alg": "HS256"`
- [ ] Signature valid? Regenerate with known-good secret
- [ ] CORS configured for Authorization? Check FastAPI middleware

---

## See Also

- [Service Startup Failures](./service-startup.md) — JWT_SECRET not set at startup
- [Docker Deployment](./docker-deployment.md) — Environment variable injection
- Source: `/src/market-data-service/auth.py` — Implementation details
