from __future__ import annotations

from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

Base = declarative_base()


def build_engine(database_url: Optional[str] = None) -> Engine:
    return create_engine(database_url or settings.database_url, future=True, pool_pre_ping=True)


def build_session_factory(database_url: Optional[str] = None) -> sessionmaker:
    return sessionmaker(bind=build_engine(database_url), autoflush=False, expire_on_commit=False)
