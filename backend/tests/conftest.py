from __future__ import annotations

import os

# Point the app at the test database before any app module reads settings.
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://intellimeet:intellimeet@localhost:5433/intellimeet_test",
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
# No live LLM calls by default; tests that exercise extraction inject a fake (or opt into Ollama).
os.environ["EXTRACTION_ENABLED"] = "false"

import pytest  # noqa: E402

from app.db import build_session_factory  # noqa: E402
from app.db_admin import ensure_database, migrate, truncate_all  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def migrated_database() -> None:
    ensure_database(TEST_DATABASE_URL)
    migrate(TEST_DATABASE_URL, from_scratch=True)


@pytest.fixture(autouse=True)
def clean_tables(migrated_database) -> None:
    truncate_all(TEST_DATABASE_URL)


@pytest.fixture
def session_factory():
    return build_session_factory(TEST_DATABASE_URL)
