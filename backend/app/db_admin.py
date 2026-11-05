"""Database setup helpers for tests and the evaluation runner (not used by the running app)."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

BACKEND_DIR = Path(__file__).resolve().parents[1]
APP_TABLES = "jobs, meetings, turns, chunks, decisions, action_items, topics, queries"


def ensure_database(url: str) -> None:
    """Create the database named in ``url`` if it does not exist."""
    target = make_url(url)
    admin = create_engine(target.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": target.database}
        ).scalar()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{target.database}"'))
    admin.dispose()


def migrate(url: str, from_scratch: bool = False) -> None:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    config.attributes["database_url"] = url
    config.attributes["configure_logger"] = False
    if from_scratch:
        command.downgrade(config, "base")
    command.upgrade(config, "head")


def truncate_all(url: str) -> None:
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {APP_TABLES} RESTART IDENTITY CASCADE"))
    engine.dispose()
