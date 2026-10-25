"""Automated tests for the Students CRUD API (pytest + FastAPI TestClient)."""

import sqlite3
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app import database
from app.main import app
from app.models import Student


def make_student(client, student_id, **overrides):
    body = {
        "student_id": student_id,
        "name": f"Student {student_id}",
        "date_of_birth": "2003-01-01",
        "email": f"{student_id.lower()}@example.com",
        "course": "Mathematics",
    }
    body.update(overrides)
    response = client.post("/students", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def count_rows(db_path):
    with sqlite3.connect(db_path) as conn:
        return conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]


def row_by_id(db_path, student_id):
    with sqlite3.connect(db_path) as conn:
        return conn.execute("SELECT * FROM students WHERE student_id = ?", (student_id,)).fetchone()


# ------------------------------------------------------------------ create


def test_create_student_returns_201_and_data(client, student_payload):
    response = client.post("/students", json=student_payload)
    assert response.status_code == 201
    assert response.json() == student_payload


def test_created_student_exists_in_database(client, student_payload, db_path):
    client.post("/students", json=student_payload)
    row = row_by_id(db_path, "S2024-001")
    assert row is not None
    assert "Aarav Sharma" in row


def test_create_with_only_required_fields_sets_optional_to_null(client):
    body = {"student_id": "MIN001", "name": "Min Student", "date_of_birth": "2000-02-29", "phone": "9876543210"}
    response = client.post("/students", json=body)
    assert response.status_code == 201
    data = response.json()
    assert data["email"] is None
    assert data["course"] is None and data["address"] is None and data["enrollment_date"] is None


@pytest.mark.parametrize("missing", ["student_id", "name", "date_of_birth"])
def test_create_rejects_missing_required_field(client, student_payload, missing, db_path):
    del student_payload[missing]
    response = client.post("/students", json=student_payload)
    assert response.status_code == 422
    assert count_rows(db_path) == 0


@pytest.mark.parametrize("email", ["not-an-email", "a@", "@example.com", "a b@example.com"])
def test_create_rejects_invalid_email(client, student_payload, email):
    student_payload["email"] = email
    assert client.post("/students", json=student_payload).status_code == 422


@pytest.mark.parametrize("dob", ["2004-13-01", "2023-02-30", "17-05-2004", "2004/05/17", "yesterday", "", 1084752000])
def test_create_rejects_invalid_dates(client, student_payload, dob):
    student_payload["date_of_birth"] = dob
    assert client.post("/students", json=student_payload).status_code == 422


def test_create_rejects_future_date_of_birth(client, student_payload, db_path):
    student_payload["date_of_birth"] = (date.today() + timedelta(days=1)).isoformat()
    response = client.post("/students", json=student_payload)
    assert response.status_code == 422
    assert count_rows(db_path) == 0


def test_create_accepts_date_of_birth_today(client, student_payload):
    student_payload["date_of_birth"] = date.today().isoformat()
    student_payload["enrollment_date"] = None
    assert client.post("/students", json=student_payload).status_code == 201


def test_create_rejects_enrollment_before_birth(client, student_payload):
    student_payload["enrollment_date"] = "2000-01-01"
    assert client.post("/students", json=student_payload).status_code == 422


@pytest.mark.parametrize("name", ["", "   ", "1234", "!!!"])
def test_create_rejects_blank_or_non_alphabetic_name(client, student_payload, name):
    student_payload["name"] = name
    assert client.post("/students", json=student_payload).status_code == 422


def test_create_rejects_too_long_name(client, student_payload):
    student_payload["name"] = "A" * 101
    assert client.post("/students", json=student_payload).status_code == 422


@pytest.mark.parametrize("student_id", ["ab", "has space", "a/b/c", "x" * 21, "", "id;DROP"])
def test_create_rejects_invalid_student_id_format(client, student_payload, student_id):
    student_payload["student_id"] = student_id
    assert client.post("/students", json=student_payload).status_code == 422


def test_create_trims_whitespace_and_lowercases_email(client, student_payload):
    student_payload.update(name="  Aarav Sharma  ", course="  Computer Science ", email="  Aarav.Sharma@Example.COM ")
    data = client.post("/students", json=student_payload).json()
    assert data["name"] == "Aarav Sharma"
    assert data["course"] == "Computer Science"
    assert data["email"] == "aarav.sharma@example.com"


def test_create_blank_optional_text_becomes_null(client, student_payload):
    student_payload.update(course="   ", address="")
    data = client.post("/students", json=student_payload).json()
    assert data["course"] is None and data["address"] is None


def test_contact_policy_requires_email_or_phone(client, student_payload, db_path):
    student_payload["email"] = None
    student_payload["phone"] = None
    assert client.post("/students", json=student_payload).status_code == 422
    student_payload.pop("email")
    student_payload.pop("phone")
    assert client.post("/students", json=student_payload).status_code == 422
    assert count_rows(db_path) == 0


def test_contact_policy_email_only_and_phone_only_are_allowed(client):
    assert client.post("/students", json={"student_id": "EMAIL1", "name": "Em Ail", "date_of_birth": "2000-01-01", "email": "em@example.com"}).status_code == 201
    assert client.post("/students", json={"student_id": "PHONE1", "name": "Pho Ne", "date_of_birth": "2000-01-01", "phone": "+1 (555) 123-4567"}).status_code == 201


@pytest.mark.parametrize("phone", ["abc", "123", "12345678901234567890", "555-CALL-NOW", "++1234567"])
def test_create_rejects_invalid_phone(client, student_payload, phone):
    student_payload["phone"] = phone
    assert client.post("/students", json=student_payload).status_code == 422


def test_create_rejects_unknown_fields(client, student_payload):
    student_payload["gpa"] = 4.0
    assert client.post("/students", json=student_payload).status_code == 422


def test_create_rejects_malformed_json(client):
    response = client.post("/students", content="{not json", headers={"Content-Type": "application/json"})
    assert response.status_code == 422


def test_duplicate_student_id_returns_409_and_keeps_original(client, student_payload, created, db_path):
    other = {**student_payload, "name": "Someone Else", "email": "other@example.com"}
    response = client.post("/students", json=other)
    assert response.status_code == 409
    assert "student_id" in response.json()["detail"]
    assert count_rows(db_path) == 1
    assert client.get("/students/S2024-001").json()["name"] == "Aarav Sharma"


def test_duplicate_email_policy_returns_409_case_insensitive(client, created, student_payload):
    other = {**student_payload, "student_id": "S2024-002", "email": created["email"].upper()}
    response = client.post("/students", json=other)
    assert response.status_code == 409
    assert "email" in response.json()["detail"]


def test_two_students_without_email_are_allowed(client):
    for sid in ("NOEMAIL1", "NOEMAIL2"):
        body = {"student_id": sid, "name": "No Email", "date_of_birth": "2000-01-01", "phone": "9876543210"}
        assert client.post("/students", json=body).status_code == 201


def test_sql_injection_text_is_stored_literally(client, student_payload, db_path):
    student_payload["name"] = "Robert'); DROP TABLE students;--"
    assert client.post("/students", json=student_payload).status_code == 201
    assert count_rows(db_path) == 1
    assert client.get("/students/S2024-001").json()["name"] == "Robert'); DROP TABLE students;--"


# -------------------------------------------------------------------- read


def test_list_empty_database_returns_empty_list(client):
    response = client.get("/students")
    assert response.status_code == 200
    assert response.json() == []
    assert response.headers["X-Total-Count"] == "0"


def test_list_returns_all_students_ordered_by_id(client):
    for sid in ("S003", "S001", "S002"):
        make_student(client, sid)
    response = client.get("/students")
    assert response.status_code == 200
    assert [s["student_id"] for s in response.json()] == ["S001", "S002", "S003"]
    assert response.headers["X-Total-Count"] == "3"


def test_get_student_by_id_returns_the_right_record(client):
    make_student(client, "S001", name="First One")
    make_student(client, "S002", name="Second One")
    response = client.get("/students/S002")
    assert response.status_code == 200
    assert response.json()["student_id"] == "S002"
    assert response.json()["name"] == "Second One"


def test_get_unknown_student_returns_404(client, created):
    response = client.get("/students/DOES-NOT-EXIST")
    assert response.status_code == 404
    assert response.json() == {"detail": "Student not found"}


def test_get_student_id_is_case_sensitive_exact_match(client, created):
    assert client.get("/students/s2024-001").status_code == 404
    assert client.get("/students/S2024-00").status_code == 404


def test_filter_by_name_is_case_insensitive_partial(client):
    make_student(client, "S001", name="Priya Nair")
    make_student(client, "S002", name="Rohan Mehta")
    names = [s["name"] for s in client.get("/students", params={"name": "PRIYA"}).json()]
    assert names == ["Priya Nair"]
    assert len(client.get("/students", params={"name": "a"}).json()) == 2


def test_filter_by_course(client):
    make_student(client, "S001", course="Computer Science")
    make_student(client, "S002", course="Mathematics")
    make_student(client, "S003", course="Applied Computer Engineering")
    ids = [s["student_id"] for s in client.get("/students", params={"course": "computer"}).json()]
    assert ids == ["S001", "S003"]


def test_filter_by_email_exact_case_insensitive(client):
    make_student(client, "S001", email="one@example.com")
    make_student(client, "S002", email="two@example.com")
    ids = [s["student_id"] for s in client.get("/students", params={"email": "ONE@example.com"}).json()]
    assert ids == ["S001"]
    assert client.get("/students", params={"email": "one@example"}).json() == []


def test_filter_by_date_of_birth(client):
    make_student(client, "S001", date_of_birth="2001-03-04")
    make_student(client, "S002", date_of_birth="2002-03-04")
    ids = [s["student_id"] for s in client.get("/students", params={"date_of_birth": "2002-03-04"}).json()]
    assert ids == ["S002"]


def test_filters_can_be_combined(client):
    make_student(client, "S001", name="Anna Lee", course="Physics")
    make_student(client, "S002", name="Anna Kim", course="Chemistry")
    result = client.get("/students", params={"name": "anna", "course": "chem"}).json()
    assert [s["student_id"] for s in result] == ["S002"]


def test_filter_wildcards_are_treated_literally(client):
    make_student(client, "S001", name="Plain Name")
    assert client.get("/students", params={"name": "%"}).json() == []
    assert client.get("/students", params={"name": "_lain"}).json() == []


def test_filter_with_no_match_returns_empty_list(client, created):
    response = client.get("/students", params={"name": "nobody-here"})
    assert response.status_code == 200
    assert response.json() == []


def test_filter_invalid_date_returns_422(client):
    assert client.get("/students", params={"date_of_birth": "2002-99-99"}).status_code == 422


def test_pagination_limit_and_offset(client):
    for i in range(1, 6):
        make_student(client, f"S00{i}")
    page = client.get("/students", params={"limit": 2, "offset": 1})
    assert [s["student_id"] for s in page.json()] == ["S002", "S003"]
    assert page.headers["X-Total-Count"] == "5"
    assert client.get("/students", params={"offset": 4, "limit": 10}).json()[0]["student_id"] == "S005"
    assert client.get("/students", params={"offset": 50}).json() == []


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": -1}, {"limit": 501}, {"offset": -1}, {"limit": "abc"}, {"offset": "x"}])
def test_invalid_pagination_parameters_return_422(client, params):
    assert client.get("/students", params=params).status_code == 422


# ------------------------------------------------------------------ update


def full_update_body(**overrides):
    body = {
        "name": "Aarav K. Sharma",
        "date_of_birth": "2004-05-18",
        "email": "aarav.new@example.com",
        "phone": "9000000000",
        "course": "Data Science",
        "address": "99 New Road, Pune",
        "enrollment_date": "2023-01-15",
    }
    body.update(overrides)
    return body


def test_put_replaces_all_editable_fields(client, created):
    response = client.put("/students/S2024-001", json=full_update_body())
    assert response.status_code == 200
    assert response.json() == {"student_id": "S2024-001", **full_update_body()}
    assert client.get("/students/S2024-001").json() == response.json()


def test_put_omitted_optional_fields_are_cleared(client, created):
    body = {"name": "Aarav Sharma", "date_of_birth": "2004-05-17", "email": "aarav.sharma@example.com"}
    data = client.put("/students/S2024-001", json=body).json()
    assert data["course"] is None and data["address"] is None and data["phone"] is None


def test_put_unknown_student_returns_404(client):
    assert client.put("/students/NOPE123", json=full_update_body()).status_code == 404


def test_put_rejects_student_id_in_body(client, created):
    response = client.put("/students/S2024-001", json={"student_id": "HACKED1", **full_update_body()})
    assert response.status_code == 422
    assert client.get("/students/HACKED1").status_code == 404
    assert client.get("/students/S2024-001").json()["name"] == "Aarav Sharma"


def test_put_missing_required_field_returns_422_and_changes_nothing(client, created):
    body = full_update_body()
    del body["name"]
    assert client.put("/students/S2024-001", json=body).status_code == 422
    assert client.get("/students/S2024-001").json() == created


@pytest.mark.parametrize(
    "bad",
    [{"email": "bad-email"}, {"date_of_birth": "2030-01-01"}, {"date_of_birth": "2004-02-31"}, {"name": "  "}, {"phone": "abc"}],
)
def test_put_invalid_values_rejected_and_record_unchanged(client, created, bad, db_path):
    before = row_by_id(db_path, "S2024-001")
    assert client.put("/students/S2024-001", json=full_update_body(**bad)).status_code == 422
    assert row_by_id(db_path, "S2024-001") == before
    assert client.get("/students/S2024-001").json() == created


def test_put_requires_a_contact_method(client, created):
    body = full_update_body(email=None, phone=None)
    assert client.put("/students/S2024-001", json=body).status_code == 422
    assert client.get("/students/S2024-001").json() == created


def test_put_duplicate_email_returns_409_and_keeps_data(client, created):
    make_student(client, "S002", email="taken@example.com")
    response = client.put("/students/S2024-001", json=full_update_body(email="taken@example.com"))
    assert response.status_code == 409
    assert client.get("/students/S2024-001").json() == created


def test_put_keeping_own_email_is_not_a_conflict(client, created):
    response = client.put("/students/S2024-001", json=full_update_body(email=created["email"]))
    assert response.status_code == 200


def test_patch_updates_only_selected_fields_and_preserves_others(client, created):
    response = client.patch("/students/S2024-001", json={"course": "Data Science"})
    assert response.status_code == 200
    assert response.json() == {**created, "course": "Data Science"}
    assert client.get("/students/S2024-001").json() == {**created, "course": "Data Science"}


def test_patch_multiple_fields(client, created):
    data = client.patch("/students/S2024-001", json={"name": "New Name", "address": "New Address"}).json()
    assert data["name"] == "New Name" and data["address"] == "New Address"
    assert data["email"] == created["email"] and data["date_of_birth"] == created["date_of_birth"]


def test_patch_can_clear_optional_field_with_null(client, created):
    data = client.patch("/students/S2024-001", json={"address": None}).json()
    assert data["address"] is None
    assert data["name"] == created["name"]


def test_patch_unknown_student_returns_404(client):
    assert client.patch("/students/NOPE123", json={"course": "X"}).status_code == 404


def test_patch_empty_body_is_rejected(client, created):
    assert client.patch("/students/S2024-001", json={}).status_code == 422


def test_patch_cannot_change_student_id(client, created):
    response = client.patch("/students/S2024-001", json={"student_id": "CHANGED1"})
    assert response.status_code == 422
    assert client.get("/students/CHANGED1").status_code == 404
    assert client.get("/students/S2024-001").json() == created


@pytest.mark.parametrize(
    "bad",
    [{"email": "nope"}, {"date_of_birth": "2999-01-01"}, {"name": None}, {"name": "   "}, {"date_of_birth": None}, {"phone": "x"}],
)
def test_patch_invalid_values_rejected_and_record_unchanged(client, created, bad, db_path):
    before = row_by_id(db_path, "S2024-001")
    response = client.patch("/students/S2024-001", json={"course": "Should Not Save", **bad})
    assert response.status_code == 422
    assert row_by_id(db_path, "S2024-001") == before
    assert client.get("/students/S2024-001").json() == created


def test_patch_final_record_must_still_have_a_contact_method(client, created):
    # created has email AND phone: removing one is fine, removing both is not.
    assert client.patch("/students/S2024-001", json={"email": None}).status_code == 200
    response = client.patch("/students/S2024-001", json={"phone": None})
    assert response.status_code == 422
    assert client.get("/students/S2024-001").json()["phone"] == created["phone"]


def test_patch_final_dates_are_validated_together(client, created):
    # enrollment_date alone is fine, but not before the stored date_of_birth.
    response = client.patch("/students/S2024-001", json={"enrollment_date": "1990-01-01"})
    assert response.status_code == 422
    assert client.get("/students/S2024-001").json() == created


def test_patch_duplicate_email_returns_409(client, created):
    make_student(client, "S002", email="taken@example.com")
    assert client.patch("/students/S2024-001", json={"email": "taken@example.com"}).status_code == 409
    assert client.get("/students/S2024-001").json() == created


def test_update_does_not_touch_other_students(client, created):
    other = make_student(client, "S002", name="Other Person")
    client.put("/students/S2024-001", json=full_update_body())
    client.patch("/students/S2024-001", json={"course": "Changed"})
    assert client.get("/students/S002").json() == other


# ------------------------------------------------------------------ delete


def test_delete_student_returns_204_with_empty_body(client, created, db_path):
    response = client.delete("/students/S2024-001")
    assert response.status_code == 204
    assert response.content == b""
    assert row_by_id(db_path, "S2024-001") is None
    assert count_rows(db_path) == 0


def test_deleted_student_cannot_be_retrieved_or_listed(client, created):
    client.delete("/students/S2024-001")
    assert client.get("/students/S2024-001").status_code == 404
    assert client.get("/students").json() == []


def test_delete_unknown_student_returns_404(client, created, db_path):
    assert client.delete("/students/NOPE123").status_code == 404
    assert count_rows(db_path) == 1


def test_delete_twice_returns_404_the_second_time(client, created):
    assert client.delete("/students/S2024-001").status_code == 204
    assert client.delete("/students/S2024-001").status_code == 404


def test_delete_only_removes_the_requested_student(client):
    make_student(client, "S001")
    make_student(client, "S002")
    client.delete("/students/S001")
    assert [s["student_id"] for s in client.get("/students").json()] == ["S002"]


def test_id_can_be_reused_after_delete(client, student_payload, created):
    client.delete("/students/S2024-001")
    assert client.post("/students", json=student_payload).status_code == 201


# ------------------------------------------- persistence / integration / docs


def test_init_db_creates_file_and_students_table(tmp_path):
    path = tmp_path / "nested" / "fresh.db"
    engine = database.make_engine(path)
    assert not path.exists()
    database.init_db(engine)
    assert path.exists()
    assert "students" in inspect(engine).get_table_names()
    engine.dispose()


def test_init_db_is_safe_to_run_twice_and_keeps_data(tmp_path):
    engine = database.make_engine(tmp_path / "again.db")
    database.init_db(engine)
    with Session(engine) as session:
        session.add(Student(student_id="KEEP1", name="Keep Me", date_of_birth=date(2000, 1, 1), phone="9876543210"))
        session.commit()
    database.init_db(engine)
    with Session(engine) as session:
        assert session.get(Student, "KEEP1") is not None
    engine.dispose()


def test_records_persist_across_connections(client, student_payload, test_engine, db_path):
    client.post("/students", json=student_payload)
    test_engine.dispose()  # close every pooled connection, like a restart
    new_engine = database.make_engine(db_path)
    with Session(new_engine) as session:
        student = session.scalars(select(Student)).one()
        assert student.student_id == "S2024-001"
        assert student.date_of_birth == date(2004, 5, 17)
    new_engine.dispose()


def test_records_persist_across_application_restart(db_path, student_payload, monkeypatch):
    """Simulate stop/start: new engine, real start-up (lifespan) event, same file."""
    from app.dependencies import get_db  # local import keeps the test self-contained

    def run_app_once(action):
        engine = database.make_engine(db_path)
        monkeypatch.setattr(database, "engine", engine)
        monkeypatch.setattr(database, "SessionLocal", database.sessionmaker(bind=engine, expire_on_commit=False))
        app.dependency_overrides.pop(get_db, None)
        try:
            with TestClient(app) as test_client:  # runs the start-up event
                return action(test_client)
        finally:
            engine.dispose()

    assert run_app_once(lambda c: c.post("/students", json=student_payload).status_code) == 201
    listed = run_app_once(lambda c: c.get("/students").json())
    assert [s["student_id"] for s in listed] == ["S2024-001"]


def test_startup_creates_database_automatically(tmp_path, monkeypatch):
    path = tmp_path / "auto" / "startup.db"
    engine = database.make_engine(path)
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", database.sessionmaker(bind=engine, expire_on_commit=False))
    assert not path.exists()
    with TestClient(app) as test_client:
        assert test_client.get("/students").json() == []
    assert path.exists()
    engine.dispose()


def test_tests_use_isolated_database_not_the_development_database(client, test_engine, db_path, student_payload):
    client.post("/students", json=student_payload)
    assert test_engine.url.database == db_path.as_posix()
    assert db_path.resolve() != database.DEFAULT_DB_PATH.resolve()
    assert count_rows(db_path) == 1


def test_db_path_resolves_independently_of_working_directory(monkeypatch, tmp_path):
    monkeypatch.delenv("STUDENTS_DB_PATH", raising=False)
    monkeypatch.chdir(tmp_path)
    assert database.resolve_db_path() == database.DEFAULT_DB_PATH
    assert database.DEFAULT_DB_PATH.is_absolute()
    monkeypatch.setenv("STUDENTS_DB_PATH", "custom/my.db")
    assert database.resolve_db_path() == (database.BASE_DIR / "custom" / "my.db").resolve()


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_swagger_redoc_and_openapi_are_available_with_all_routes(client):
    assert client.get("/docs").status_code == 200
    assert client.get("/redoc").status_code == 200
    spec = client.get("/openapi.json").json()
    assert spec["info"]["title"] == "Students Database CRUD API"
    paths = spec["paths"]
    assert set(paths["/students"]) == {"get", "post"}
    assert set(paths["/students/{student_id}"]) == {"get", "put", "patch", "delete"}
    assert "/health" in paths


def test_core_endpoints_work_without_ollama(client, created):
    # The project has no Ollama code or dependency; all CRUD routes work on their own.
    assert client.get("/students").status_code == 200
    assert client.get("/students/S2024-001").status_code == 200
    import sys

    assert "ollama" not in sys.modules


def test_unexpected_server_error_returns_generic_500_without_details(client, monkeypatch):
    from app import crud

    def boom(*args, **kwargs):
        raise RuntimeError("secret internal path C:/Users/x/students.db")

    monkeypatch.setattr(crud, "list_students", boom)
    safe_client = TestClient(app, raise_server_exceptions=False)
    response = safe_client.get("/students")
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    assert "secret" not in response.text and "students.db" not in response.text


def test_database_enforces_unique_student_id_itself(test_engine):
    from sqlalchemy.exc import IntegrityError

    with Session(test_engine) as session:
        session.add(Student(student_id="DUP001", name="One", date_of_birth=date(2000, 1, 1), phone="9876543210"))
        session.commit()
    with Session(test_engine) as session:
        session.add(Student(student_id="DUP001", name="Two", date_of_birth=date(2000, 1, 1), phone="9876543210"))
        with pytest.raises(IntegrityError):
            session.commit()
