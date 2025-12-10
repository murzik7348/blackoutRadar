"""Database utilities for the outage bot."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Callable

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import scoped_session, sessionmaker


def create_engine_from_url(database_url: str) -> Engine:
    """Create a SQLAlchemy engine."""

    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, future=True, connect_args=connect_args)


def create_session_factory(engine: Engine) -> Callable[[], scoped_session]:
    """Build a session factory bound to the provided engine."""

    return scoped_session(sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True))


@contextmanager
def session_scope(session_factory: Callable[[], scoped_session]):
    """Provide a transactional scope around a series of operations."""

    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
