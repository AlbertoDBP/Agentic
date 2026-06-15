-- Runs automatically on the postgres container's FIRST start (empty data dir).
-- The pg_dump restore also recreates these, but pre-creating them verifies the
-- pgvector image supports the `vector` extension before you restore.
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_trgm;
