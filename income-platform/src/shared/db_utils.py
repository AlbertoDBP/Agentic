"""
income-platform shared utilities — database URL helpers.
Canonical implementations imported (or copied) by each service.
"""


def build_sync_url(raw_url: str) -> str:
    """Strip ?sslmode=... from a PostgreSQL URL for psycopg2.
    SSL mode is passed separately via connect_args={'sslmode': 'require'}.
    """
    if "?" in raw_url:
        return raw_url.split("?")[0]
    return raw_url


def build_async_url(raw_url: str) -> str:
    """Convert a psycopg2-style PostgreSQL URL to asyncpg format and strip SSL params.
    Replaces postgresql+psycopg2:// and postgresql+asyncpg:// prefixes with postgresql://
    and strips ?sslmode=... query string (SSL passed via connect_args={'ssl': 'require'}).
    """
    url = raw_url
    url = url.replace("postgresql+psycopg2://", "postgresql://")
    url = url.replace("postgresql+asyncpg://", "postgresql://")
    if "?" in url:
        url = url.split("?")[0]
    return url
