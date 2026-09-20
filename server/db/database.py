from __future__ import annotations

import os

from sqlalchemy import create_engine


def _database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not configured")
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    elif url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    return url


engine = create_engine(_database_url(), pool_pre_ping=True)