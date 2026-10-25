"""Database operations. No HTTP code here: errors are raised as plain Python exceptions.

Every write is committed on success and rolled back on failure, so a failed
operation never leaves a half-modified record behind.
"""

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Student
from app.schemas import StudentCreate, StudentPatch, StudentUpdate


class DuplicateStudentError(Exception):
    """student_id or email already belongs to another student."""

    def __init__(self, field: str):
        self.field = field
        super().__init__(f"A student with this {field} already exists")


def _escape_like(text: str) -> str:
    """Escape LIKE wildcards so user text is matched literally."""
    return text.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")


def get_student(db: Session, student_id: str) -> Student | None:
    return db.get(Student, student_id)


def _email_taken(db: Session, email: str | None, exclude_id: str | None = None) -> bool:
    if not email:
        return False
    stmt = select(Student.student_id).where(Student.email == email)
    if exclude_id is not None:
        stmt = stmt.where(Student.student_id != exclude_id)
    return db.scalar(stmt) is not None


def _commit(db: Session, conflict_field: str) -> None:
    """Commit, turning a database uniqueness violation into DuplicateStudentError."""
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise DuplicateStudentError(conflict_field) from None
    except Exception:
        db.rollback()
        raise


def list_students(
    db: Session,
    *,
    name: str | None = None,
    course: str | None = None,
    email: str | None = None,
    date_of_birth: date | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[Student], int]:
    """Return (page of students, total number matching the filters)."""
    conditions = []
    if name:
        conditions.append(Student.name.ilike(f"%{_escape_like(name)}%", escape="\\"))
    if course:
        conditions.append(Student.course.ilike(f"%{_escape_like(course)}%", escape="\\"))
    if email:
        conditions.append(Student.email == email.strip().lower())
    if date_of_birth:
        conditions.append(Student.date_of_birth == date_of_birth)

    total = db.scalar(select(func.count()).select_from(Student).where(*conditions)) or 0
    stmt = (
        select(Student)
        .where(*conditions)
        .order_by(Student.student_id)
        .limit(limit)
        .offset(offset)
    )
    return list(db.scalars(stmt)), total


def create_student(db: Session, data: StudentCreate) -> Student:
    if db.get(Student, data.student_id) is not None:
        raise DuplicateStudentError("student_id")
    if _email_taken(db, data.email):
        raise DuplicateStudentError("email")
    student = Student(**data.model_dump())
    db.add(student)
    _commit(db, "student_id or email")  # race-condition safety net
    return student


def replace_student(db: Session, student: Student, data: StudentUpdate) -> Student:
    if _email_taken(db, data.email, exclude_id=student.student_id):
        raise DuplicateStudentError("email")
    for field, value in data.model_dump().items():
        setattr(student, field, value)
    _commit(db, "email")
    return student


def merged_fields(student: Student, patch: StudentPatch) -> dict:
    """Current values overlaid with only the fields the client explicitly sent."""
    current = {
        "name": student.name,
        "date_of_birth": student.date_of_birth,
        "email": student.email,
        "phone": student.phone,
        "course": student.course,
        "address": student.address,
        "enrollment_date": student.enrollment_date,
    }
    current.update(patch.model_dump(exclude_unset=True))
    return current


def delete_student(db: Session, student: Student) -> None:
    db.delete(student)
    _commit(db, "student_id")
