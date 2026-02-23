import asyncio
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# ---------------------------------------------------------------------------
# Make service modules importable (alembic runs from src/market-data-service/)
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orm_models import Base  # noqa: E402

# ---------------------------------------------------------------------------
# Alembic config
# ---------------------------------------------------------------------------
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Only autogenerate against tables this service owns — do NOT touch
# market_data_daily or any other pre-existing platform tables.
MANAGED_TABLES = {"price_history"}

target_metadata = Base.metadata


def include_object(obj, name, type_, reflected, compare_to):
    """Restrict autogenerate to tables owned by this service."""
    if type_ == "table":
        return name in MANAGED_TABLES
    return True


def _get_url() -> str:
    """
    Build the asyncpg-compatible URL from the DATABASE_URL environment variable.
    Falls back to the alembic.ini placeholder for offline SQL generation.
    """
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        return config.get_main_option("sqlalchemy.url")

    # Ensure asyncpg driver
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)

    # asyncpg uses connect_args for SSL, not a URL parameter
    url = url.replace("?sslmode=require", "").replace("&sslmode=require", "")
    return url


# ---------------------------------------------------------------------------
# Offline mode — emits SQL to stdout without a live DB connection
# ---------------------------------------------------------------------------

def run_migrations_offline() -> None:
    context.configure(
        url=_get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# Online mode — runs against a live database
# ---------------------------------------------------------------------------

def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    url = _get_url()
    ssl_required = "sslmode=require" in os.environ.get("DATABASE_URL", "")

    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = url

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args={"ssl": "require", "timeout": 30} if ssl_required else {"timeout": 30},
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
