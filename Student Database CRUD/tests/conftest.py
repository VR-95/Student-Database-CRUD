"""Test fixtures. Every test gets its own temporary SQLite file, so the real
development database (data/students.db) is never touched."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app import database
from app.dependencies import get_db
from app.main import app


@pytest.fixture()
def db_path(tmp_path):
    return tmp_path / "test_students.db"


@pytest.fixture()
def test_engine(db_path):
    engine = database.make_engine(db_path)
    database.init_db(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def client(test_engine):
    """TestClient wired to the temporary database (no start-up event is run)."""
    TestSession = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture()
def student_payload():
    """A valid POST /students body. Returns a fresh copy for each test."""
    return {
        "student_id": "S2024-001",
        "name": "Aarav Sharma",
        "date_of_birth": "2004-05-17",
        "email": "aarav.sharma@example.com",
        "phone": "+91 98765 43210",
        "course": "Computer Science",
        "address": "12 Example Street, Mumbai",
        "enrollment_date": "2022-08-01",
    }


@pytest.fixture()
def created(client, student_payload):
    """A student that already exists in the database."""
    response = client.post("/students", json=student_payload)
    assert response.status_code == 201
    return response.json()
