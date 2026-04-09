# src/admin-panel/app/routes/api_chat.py
"""
Chat assistant CRUD — threads, messages, memories, skills.
Tables are created on startup via ensure_chat_tables().
"""
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from typing import Optional

from app.database import engine

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Table migration ────────────────────────────────────────────────────────────

def ensure_chat_tables():
    """Create chat tables if they don't exist. Called once at startup."""
    ddl = """
    CREATE TABLE IF NOT EXISTS platform_shared.chat_threads (
        id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id    TEXT NOT NULL DEFAULT 'default',
        title      TEXT,
        created_at TIMESTAMPTZ DEFAULT now(),
        updated_at TIMESTAMPTZ DEFAULT now()
    );
    CREATE INDEX IF NOT EXISTS chat_threads_user_updated
        ON platform_shared.chat_threads (user_id, updated_at DESC);

    CREATE TABLE IF NOT EXISTS platform_shared.chat_messages (
        id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        thread_id  UUID REFERENCES platform_shared.chat_threads(id) ON DELETE CASCADE,
        role       TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
        raw        JSONB NOT NULL,
        created_at TIMESTAMPTZ DEFAULT now()
    );
    CREATE INDEX IF NOT EXISTS chat_messages_thread_created
        ON platform_shared.chat_messages (thread_id, created_at ASC);

    CREATE TABLE IF NOT EXISTS platform_shared.user_memories (
        id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id    TEXT NOT NULL DEFAULT 'default',
        content    TEXT NOT NULL,
        category   TEXT,
        created_at TIMESTAMPTZ DEFAULT now()
    );

    CREATE TABLE IF NOT EXISTS platform_shared.user_skills (
        id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id         TEXT NOT NULL DEFAULT 'default',
        name            TEXT NOT NULL,
        trigger_phrase  TEXT NOT NULL,
        procedure       TEXT NOT NULL,
        created_at      TIMESTAMPTZ DEFAULT now()
    );
    """
    try:
        with engine.connect() as conn:
            conn.execute(text(ddl))
            conn.commit()
        logger.info("chat tables ready")
    except Exception as exc:
        logger.error("ensure_chat_tables failed: %s", exc)


# ── Pydantic models ────────────────────────────────────────────────────────────

class ThreadCreate(BaseModel):
    title: Optional[str] = None

class MessageItem(BaseModel):
    role: str
    raw: dict

class MemoryCreate(BaseModel):
    content: str
    category: Optional[str] = None

class SkillCreate(BaseModel):
    name: str
    trigger_phrase: str
    procedure: str


# ── Threads ────────────────────────────────────────────────────────────────────

@router.post("/api/chat/threads")
def create_thread(body: ThreadCreate):
    with engine.connect() as conn:
        row = conn.execute(text(
            "INSERT INTO platform_shared.chat_threads (title) VALUES (:title) RETURNING id, title, created_at"
        ), {"title": body.title}).fetchone()
        conn.commit()
    return {"id": str(row.id), "title": row.title, "created_at": row.created_at.isoformat()}


@router.get("/api/chat/threads")
def list_threads():
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT id, title, created_at, updated_at FROM platform_shared.chat_threads "
            "WHERE user_id = 'default' ORDER BY updated_at DESC LIMIT 100"
        )).fetchall()
    return [{"id": str(r.id), "title": r.title, "created_at": r.created_at.isoformat(),
             "updated_at": r.updated_at.isoformat()} for r in rows]


# ── Messages ───────────────────────────────────────────────────────────────────

@router.post("/api/chat/threads/{thread_id}/messages")
def append_messages(thread_id: str, messages: list[MessageItem]):
    import json
    with engine.connect() as conn:
        for msg in messages:
            conn.execute(text(
                "INSERT INTO platform_shared.chat_messages (thread_id, role, raw) "
                "VALUES (:tid, :role, :raw::jsonb)"
            ), {"tid": thread_id, "role": msg.role, "raw": json.dumps(msg.raw)})
        conn.execute(text(
            "UPDATE platform_shared.chat_threads SET updated_at = now() WHERE id = :id"
        ), {"id": thread_id})
        conn.commit()
    return {"saved": len(messages)}


@router.get("/api/chat/threads/{thread_id}/messages")
def get_messages(thread_id: str):
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT id, role, raw, created_at FROM platform_shared.chat_messages "
            "WHERE thread_id = :tid ORDER BY created_at ASC"
        ), {"tid": thread_id}).fetchall()
    return [{"id": str(r.id), "role": r.role, "raw": r.raw,
             "created_at": r.created_at.isoformat()} for r in rows]


# ── Memories ───────────────────────────────────────────────────────────────────

@router.post("/api/chat/memories")
def create_memory(body: MemoryCreate):
    with engine.connect() as conn:
        row = conn.execute(text(
            "INSERT INTO platform_shared.user_memories (content, category) "
            "VALUES (:content, :category) RETURNING id, content, category, created_at"
        ), {"content": body.content, "category": body.category}).fetchone()
        conn.commit()
    return {"id": str(row.id), "content": row.content, "category": row.category,
            "created_at": row.created_at.isoformat()}


@router.get("/api/chat/memories")
def list_memories():
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT id, content, category, created_at FROM platform_shared.user_memories "
            "WHERE user_id = 'default' ORDER BY created_at DESC"
        )).fetchall()
    return [{"id": str(r.id), "content": r.content, "category": r.category,
             "created_at": r.created_at.isoformat()} for r in rows]


@router.delete("/api/chat/memories/{memory_id}")
def delete_memory(memory_id: str):
    with engine.connect() as conn:
        conn.execute(text(
            "DELETE FROM platform_shared.user_memories WHERE id = :id"
        ), {"id": memory_id})
        conn.commit()
    return {"deleted": memory_id}


# ── Skills ─────────────────────────────────────────────────────────────────────

@router.post("/api/chat/skills")
def create_skill(body: SkillCreate):
    with engine.connect() as conn:
        row = conn.execute(text(
            "INSERT INTO platform_shared.user_skills (name, trigger_phrase, procedure) "
            "VALUES (:name, :trigger, :procedure) RETURNING id, name, trigger_phrase, procedure, created_at"
        ), {"name": body.name, "trigger": body.trigger_phrase, "procedure": body.procedure}).fetchone()
        conn.commit()
    return {"id": str(row.id), "name": row.name, "trigger_phrase": row.trigger_phrase,
            "procedure": row.procedure, "created_at": row.created_at.isoformat()}


@router.get("/api/chat/skills")
def list_skills():
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT id, name, trigger_phrase, procedure, created_at FROM platform_shared.user_skills "
            "WHERE user_id = 'default' ORDER BY created_at DESC"
        )).fetchall()
    return [{"id": str(r.id), "name": r.name, "trigger_phrase": r.trigger_phrase,
             "procedure": r.procedure, "created_at": r.created_at.isoformat()} for r in rows]


@router.delete("/api/chat/skills/{skill_id}")
def delete_skill(skill_id: str):
    with engine.connect() as conn:
        conn.execute(text(
            "DELETE FROM platform_shared.user_skills WHERE id = :id"
        ), {"id": skill_id})
        conn.commit()
    return {"deleted": skill_id}
