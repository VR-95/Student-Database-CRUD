"""SQLAlchemy table definitions (database layer only; API schemas live in schemas.py)."""

from datetime import date

from sqlalchemy import Date, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Student(Base):
    __tablename__ = "students"

    # Client-supplied string ID, e.g. "S2024-001". Unique because it is the primary key.
    student_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)
    # Stored lower-case. UNIQUE in SQLite; many rows may have NULL (no email).
    email: Mapped[str | None] = mapped_column(String(254), unique=True, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    course: Mapped[str | None] = mapped_column(String(100), nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    enrollment_date: Mapped[date | None] = mapped_column(Date, nullable=True)
