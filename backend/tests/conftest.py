"""Pytest fixtures shared across the suite.

We run every test against a fresh in-memory SQLite database. Each fixture
spins up the engine + migrations once per session, then a fresh `session`
per test (rolled back at teardown). This means tests can never poison
each other and they run in milliseconds.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Make `app` importable when running `pytest` from the backend dir.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Force a clean ephemeral DB before any module import that creates the engine.
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import pytest  # noqa: E402
from sqlmodel import Session, SQLModel  # noqa: E402


@pytest.fixture(scope="session")
def engine():
    from app.db.session import engine as real_engine, init_db

    init_db()
    yield real_engine
    SQLModel.metadata.drop_all(real_engine)


@pytest.fixture
def session(engine):
    """Per-test session. We don't use SAVEPOINT rollbacks here — instead each
    test that mutates state gets a freshly-truncated set of tables. Simpler
    than nested transactions and our test surface area is small."""
    with Session(engine) as s:
        yield s
        s.rollback()
    # Truncate everything between tests so state never leaks.
    with engine.begin() as conn:
        for table in reversed(SQLModel.metadata.sorted_tables):
            conn.exec_driver_sql(f"DELETE FROM {table.name}")
