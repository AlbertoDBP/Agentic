"""
Tests for the JWT authentication layer (auth.py + FastAPI dependency injection).

Every protected endpoint uses ``Depends(verify_token)``.  We exercise the auth
path via GET /stocks/AAPL/price because it is the simplest protected route.

Covers:
  - Missing Authorization header → 403 (HTTPBearer auto_error=True)
  - Non-Bearer scheme (Basic auth) → 403
  - Malformed token (wrong number of segments) → 401
  - Token signed with wrong secret → 401
  - Expired token (exp in the past) → 401
  - Valid token → 200 (request proceeds to the mocked service)
  - Token with no 'exp' claim → 200 (auth.py only checks exp when present)
  - JWT_SECRET env var absent → 503

All tests use the `client` fixture (mocked service layer) so no real DB/Redis
or external API calls occur.
"""
import base64
import hashlib
import hmac
import json
import os
import time

import pytest

# Re-use the make_token helper from conftest
from conftest import make_token


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PRICE_URL = "/stocks/AAPL/price"


def _make_token_custom(
    header_dict: dict | None = None,
    payload_dict: dict | None = None,
    secret: str = "test-secret",
    skip_sig: bool = False,
    bad_sig: bool = False,
) -> str:
    """Low-level token builder for negative-case testing."""
    if header_dict is None:
        header_dict = {"alg": "HS256", "typ": "JWT"}
    if payload_dict is None:
        payload_dict = {"sub": "test", "exp": int(time.time()) + 3600}

    header  = base64.urlsafe_b64encode(json.dumps(header_dict).encode()).rstrip(b"=").decode()
    payload = base64.urlsafe_b64encode(json.dumps(payload_dict).encode()).rstrip(b"=").decode()

    if skip_sig:
        return f"{header}.{payload}"

    signing_secret = "wrong-secret" if bad_sig else secret
    sig = (
        base64.urlsafe_b64encode(
            hmac.new(
                signing_secret.encode(),
                f"{header}.{payload}".encode(),
                hashlib.sha256,
            ).digest()
        )
        .rstrip(b"=")
        .decode()
    )
    return f"{header}.{payload}.{sig}"


# ---------------------------------------------------------------------------
# Missing / malformed Authorization header → 403
# ---------------------------------------------------------------------------

class TestMissingAuthHeader:
    def test_no_header_returns_403(self, client):
        resp = client.get(_PRICE_URL)
        assert resp.status_code == 403

    def test_empty_bearer_returns_403(self, client):
        resp = client.get(_PRICE_URL, headers={"Authorization": ""})
        assert resp.status_code == 403

    def test_basic_auth_scheme_returns_403(self, client):
        """HTTPBearer rejects non-Bearer schemes."""
        resp = client.get(_PRICE_URL, headers={"Authorization": "Basic dXNlcjpwYXNz"})
        assert resp.status_code == 403

    def test_bearer_without_token_returns_403(self, client):
        resp = client.get(_PRICE_URL, headers={"Authorization": "Bearer "})
        # FastAPI HTTPBearer treats an empty credential as a missing header
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Structurally invalid token → 401
# ---------------------------------------------------------------------------

class TestInvalidTokenStructure:
    def test_random_string_token_returns_401(self, client):
        resp = client.get(_PRICE_URL, headers={"Authorization": "Bearer notavalidtoken"})
        assert resp.status_code == 401

    def test_only_two_segments_returns_401(self, client):
        token = _make_token_custom(skip_sig=True)   # header.payload (no sig)
        resp  = client.get(_PRICE_URL, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401

    def test_four_segments_returns_401(self, client):
        token = make_token() + ".extrasegment"
        resp  = client.get(_PRICE_URL, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Valid structure but wrong signature → 401
# ---------------------------------------------------------------------------

class TestWrongSignature:
    def test_token_signed_with_wrong_secret_returns_401(self, client):
        token = _make_token_custom(bad_sig=True)
        resp  = client.get(_PRICE_URL, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401

    def test_tampered_payload_invalidates_signature(self, client):
        """Modify the payload segment in-place; signature no longer matches."""
        original = make_token()
        parts    = original.split(".")
        # Replace payload with a different encoded value
        tampered_payload = (
            base64.urlsafe_b64encode(
                json.dumps({"sub": "attacker", "exp": int(time.time()) + 9999}).encode()
            )
            .rstrip(b"=")
            .decode()
        )
        tampered_token = f"{parts[0]}.{tampered_payload}.{parts[2]}"
        resp = client.get(_PRICE_URL, headers={"Authorization": f"Bearer {tampered_token}"})
        assert resp.status_code == 401

    def test_tampered_header_invalidates_signature(self, client):
        """Modify the header segment; HMAC input changes so signature fails."""
        original = make_token()
        parts    = original.split(".")
        new_header = (
            base64.urlsafe_b64encode(
                json.dumps({"alg": "HS256", "typ": "JWT", "extra": "injected"}).encode()
            )
            .rstrip(b"=")
            .decode()
        )
        tampered_token = f"{new_header}.{parts[1]}.{parts[2]}"
        resp = client.get(_PRICE_URL, headers={"Authorization": f"Bearer {tampered_token}"})
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Expired token → 401
# ---------------------------------------------------------------------------

class TestExpiredToken:
    def test_expired_token_returns_401(self, client):
        token = make_token(exp_offset=-1)    # exp is 1 second in the past
        resp  = client.get(_PRICE_URL, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401

    def test_expired_token_error_message(self, client):
        token = make_token(exp_offset=-3600)  # expired 1 hour ago
        resp  = client.get(_PRICE_URL, headers={"Authorization": f"Bearer {token}"})
        body  = resp.json()
        assert "detail" in body
        # auth.py raises "Token has expired" for expired tokens
        assert "expired" in body["detail"].lower()

    def test_far_future_token_is_valid(self, client):
        """Token expiring in 24 hours should be accepted."""
        token = make_token(exp_offset=86400)
        resp  = client.get(_PRICE_URL, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Valid token variations → 200
# ---------------------------------------------------------------------------

class TestValidToken:
    def test_valid_token_returns_200(self, client, auth_headers):
        resp = client.get(_PRICE_URL, headers=auth_headers)
        assert resp.status_code == 200

    def test_token_without_exp_claim_is_accepted(self, client):
        """auth.py only validates exp when the key is present in the payload."""
        header  = base64.urlsafe_b64encode(
            json.dumps({"alg": "HS256", "typ": "JWT"}).encode()
        ).rstrip(b"=").decode()
        payload = base64.urlsafe_b64encode(
            json.dumps({"sub": "no-expiry-user"}).encode()
        ).rstrip(b"=").decode()
        sig = (
            base64.urlsafe_b64encode(
                hmac.new(
                    b"test-secret",
                    f"{header}.{payload}".encode(),
                    hashlib.sha256,
                ).digest()
            )
            .rstrip(b"=")
            .decode()
        )
        token = f"{header}.{payload}.{sig}"
        resp  = client.get(_PRICE_URL, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_valid_token_on_dividends_endpoint(self, client, auth_headers):
        resp = client.get("/stocks/AAPL/dividends", headers=auth_headers)
        assert resp.status_code == 200

    def test_valid_token_on_fundamentals_endpoint(self, client, auth_headers):
        resp = client.get("/stocks/AAPL/fundamentals", headers=auth_headers)
        assert resp.status_code == 200

    def test_valid_token_on_history_endpoint(self, client, auth_headers):
        resp = client.get(
            "/stocks/AAPL/history",
            params={"start_date": "2026-01-01", "end_date": "2026-03-01"},
            headers=auth_headers,
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# JWT_SECRET not configured → 503
# ---------------------------------------------------------------------------

class TestMissingJwtSecret:
    def test_missing_jwt_secret_returns_503(self, client, monkeypatch):
        """When JWT_SECRET is absent from env, verify_token raises 503."""
        monkeypatch.delenv("JWT_SECRET", raising=False)

        valid_token = make_token()
        resp = client.get(_PRICE_URL, headers={"Authorization": f"Bearer {valid_token}"})
        assert resp.status_code == 503

        # Restore so subsequent tests are not affected
        monkeypatch.setenv("JWT_SECRET", "test-secret")
