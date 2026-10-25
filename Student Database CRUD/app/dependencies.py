"""FastAPI dependencies."""

from collections.abc import Iterator

from sqlalchemy.orm import Session

from app import database


def get_db() -> Iterator[Session]:
    """Give each request its own session and always release it afterwards.

    Tests replace this dependency with one bound to a temporary database.
    """
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()
