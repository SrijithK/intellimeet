import os
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

Base = declarative_base()


def get_database_url() -> str:
    return os.getenv("DATABASE_URL", "sqlite:///:memory:")


def build_engine(database_url: Optional[str] = None):
    url = database_url or get_database_url()

    if url.startswith("sqlite"):
        return create_engine(
            url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            future=True,
        )
    return create_engine(url, future=True)


def build_session_factory(database_url: Optional[str] = None):
    engine = build_engine(database_url)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)
