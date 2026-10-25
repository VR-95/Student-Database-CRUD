"""Database configuration: engine, session factory and table initialisation.

SQLAlchemy 2.x with SQLite is used for the whole project.

The database file lives at ``<project root>/data/students.db`` by default.
Set the ``STUDENTS_DB_PATH`` environment variable to use another file. The path
is always resolved to an absolute path, so it does not depend on the directory
the terminal is currently in.
"""

import os
from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = BASE_DIR / "data" / "students.db"


class Base(DeclarativeBase):
    """Base class for all ORM models."""


def resolve_db_path() -> Path:
    """Return the absolute path of the SQLite file to use."""
    configured = os.environ.get("STUDENTS_DB_PATH")
    if configured:
        path = Path(configured).expanduser()
        if not path.is_absolute():
            path = BASE_DIR / path
        return path.resolve()
    return DEFAULT_DB_PATH


def make_engine(db_path: Path) -> Engine:
    """Create an engine for a SQLite file. Nothing touches the disk until first use."""
    return create_engine(
        f"sqlite:///{db_path.as_posix()}",
        # FastAPI may use different threads for one request; sessions are not shared.
        connect_args={"check_same_thread": False},
    )


engine: Engine = make_engine(resolve_db_path())
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db(target_engine: Engine | None = None) -> None:
    """Create the data folder and all tables if they do not exist yet.

    Safe to call on every start-up: existing tables and data are left untouched.
    """
    from app import models  # noqa: F401  (registers the models on Base.metadata)

    target = target_engine or engine
    if target.url.database:
        Path(target.url.database).parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=target)
