"""Insert a few FICTIONAL students into the development database.

Run from the project root:   python scripts/seed_data.py
Safe to run repeatedly: students that already exist are skipped.
"""

import sys
from datetime import date
from pathlib import Path

# Allow "python scripts/seed_data.py" from any directory.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app import database  # noqa: E402
from app.models import Student  # noqa: E402

SAMPLE_STUDENTS = [
    dict(student_id="DEMO-001", name="Asha Verma", date_of_birth=date(2004, 3, 12), email="asha.verma@example.com", phone="+91 90000 00001", course="Computer Science", address="1 Sample Lane, Exampleville", enrollment_date=date(2022, 8, 1)),
    dict(student_id="DEMO-002", name="Rohan Iyer", date_of_birth=date(2003, 11, 5), email="rohan.iyer@example.com", phone=None, course="Mathematics", address=None, enrollment_date=date(2021, 8, 1)),
    dict(student_id="DEMO-003", name="Meera Das", date_of_birth=date(2005, 7, 23), email=None, phone="9000000003", course="Computer Science", address="3 Test Road, Sampletown", enrollment_date=date(2023, 8, 1)),
    dict(student_id="DEMO-004", name="Kabir Singh", date_of_birth=date(2002, 1, 30), email="kabir.singh@example.com", phone="9000000004", course="Physics", address="4 Demo Street, Mockcity", enrollment_date=None),
    dict(student_id="DEMO-005", name="Isha Rao", date_of_birth=date(2006, 9, 9), email="isha.rao@example.com", phone=None, course=None, address=None, enrollment_date=None),
]


def seed() -> tuple[int, int]:
    """Return (inserted, skipped)."""
    database.init_db()
    inserted = skipped = 0
    with database.SessionLocal() as db:
        for data in SAMPLE_STUDENTS:
            email_taken = data["email"] and db.scalar(select(Student).where(Student.email == data["email"]))
            if db.get(Student, data["student_id"]) or email_taken:
                skipped += 1
                continue
            db.add(Student(**data))
            inserted += 1
        db.commit()
    return inserted, skipped


if __name__ == "__main__":
    added, skipped = seed()
    print(f"Database: {database.resolve_db_path()}")
    print(f"Inserted {added} fictional student(s), skipped {skipped} that already exist.")
