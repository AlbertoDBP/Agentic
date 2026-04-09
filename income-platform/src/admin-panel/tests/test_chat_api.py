# src/admin-panel/tests/test_chat_api.py
import pytest
from fastapi.testclient import TestClient
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# These tests require a real DB. Skip with SKIP_DB_TESTS=1.
pytestmark = pytest.mark.skipif(
    os.environ.get("SKIP_DB_TESTS") == "1",
    reason="requires database"
)

from app.main import app
client = TestClient(app)

SERVICE_TOKEN = os.environ.get("SERVICE_TOKEN", "dev-token")
HEADERS = {"Authorization": f"Bearer {SERVICE_TOKEN}"}


def test_create_thread():
    r = client.post("/api/chat/threads", json={"title": "Test thread"}, headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert "id" in data
    assert data["title"] == "Test thread"


def test_list_threads():
    r = client.get("/api/chat/threads", headers=HEADERS)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_append_and_fetch_messages():
    # Create thread
    thread = client.post("/api/chat/threads", json={"title": "msg test"}, headers=HEADERS).json()
    tid = thread["id"]

    # Append two messages
    msgs = [
        {"role": "user", "raw": {"role": "user", "content": "hello"}},
        {"role": "assistant", "raw": {"role": "assistant", "content": [{"type": "text", "text": "hi there"}]}},
    ]
    r = client.post(f"/api/chat/threads/{tid}/messages", json=msgs, headers=HEADERS)
    assert r.status_code == 200

    # Fetch
    r = client.get(f"/api/chat/threads/{tid}/messages", headers=HEADERS)
    assert r.status_code == 200
    result = r.json()
    assert len(result) == 2
    assert result[0]["role"] == "user"


def test_memory_crud():
    r = client.post("/api/chat/memories",
        json={"content": "MAIN is anchor", "category": "constraint"},
        headers=HEADERS)
    assert r.status_code == 200
    mem = r.json()
    assert "id" in mem

    r = client.get("/api/chat/memories", headers=HEADERS)
    assert any(m["id"] == mem["id"] for m in r.json())

    r = client.delete(f"/api/chat/memories/{mem['id']}", headers=HEADERS)
    assert r.status_code == 200


def test_skill_crud():
    r = client.post("/api/chat/skills", json={
        "name": "BDC Check",
        "trigger_phrase": "bdc check",
        "procedure": "Fetch BDC positions, rank by durability."
    }, headers=HEADERS)
    assert r.status_code == 200
    skill = r.json()
    assert "id" in skill

    r = client.get("/api/chat/skills", headers=HEADERS)
    assert any(s["id"] == skill["id"] for s in r.json())

    r = client.delete(f"/api/chat/skills/{skill['id']}", headers=HEADERS)
    assert r.status_code == 200
