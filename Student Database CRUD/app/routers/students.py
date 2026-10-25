"""HTTP routes for students. Handlers only translate HTTP <-> crud calls."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app import crud
from app.dependencies import get_db
from app.schemas import StudentCreate, StudentPatch, StudentRead, StudentUpdate

router = APIRouter(prefix="/students", tags=["Students"])

_NOT_FOUND = {404: {"description": "Student not found", "content": {"application/json": {"example": {"detail": "Student not found"}}}}}
_CONFLICT = {409: {"description": "Duplicate student_id or email", "content": {"application/json": {"example": {"detail": "A student with this student_id already exists"}}}}}

DbSession = Annotated[Session, Depends(get_db)]


def _get_or_404(db: Session, student_id: str):
    student = crud.get_student(db, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Student not found")
    return student


@router.post(
    "",
    response_model=StudentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a student",
    responses={**_CONFLICT},
)
def create_student(data: StudentCreate, db: DbSession):
    """Create a student. `student_id` is chosen by the client (3-20 letters, digits, `-` or `_`).

    Either `email` or `phone` is required. Duplicate `student_id` or `email` returns 409.
    """
    try:
        return crud.create_student(db, data)
    except crud.DuplicateStudentError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None


@router.get("", response_model=list[StudentRead], summary="List and filter students")
def list_students(
    response: Response,
    db: DbSession,
    name: Annotated[str | None, Query(max_length=100, description="Name contains (case-insensitive)")] = None,
    course: Annotated[str | None, Query(max_length=100, description="Course contains (case-insensitive)")] = None,
    email: Annotated[str | None, Query(max_length=254, description="Exact email (case-insensitive)")] = None,
    date_of_birth: Annotated[date | None, Query(description="Exact date of birth, YYYY-MM-DD")] = None,
    limit: Annotated[int, Query(ge=1, le=500, description="Page size")] = 100,
    offset: Annotated[int, Query(ge=0, description="Records to skip")] = 0,
):
    """Return students ordered by `student_id`. An empty database returns `[]`.

    The total number of matches (before `limit`/`offset`) is in the `X-Total-Count` header.
    """
    students, total = crud.list_students(
        db, name=name, course=course, email=email,
        date_of_birth=date_of_birth, limit=limit, offset=offset,
    )
    response.headers["X-Total-Count"] = str(total)
    return students


@router.get(
    "/{student_id}",
    response_model=StudentRead,
    summary="Get one student",
    responses={**_NOT_FOUND},
)
def get_student(student_id: str, db: DbSession):
    return _get_or_404(db, student_id)


@router.put(
    "/{student_id}",
    response_model=StudentRead,
    summary="Replace a student's editable fields",
    responses={**_NOT_FOUND, **_CONFLICT},
)
def replace_student(student_id: str, data: StudentUpdate, db: DbSession):
    """Send every editable field. `student_id` cannot be changed and must not be in the body."""
    student = _get_or_404(db, student_id)
    try:
        return crud.replace_student(db, student, data)
    except crud.DuplicateStudentError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None


@router.patch(
    "/{student_id}",
    response_model=StudentRead,
    summary="Partially update a student",
    responses={**_NOT_FOUND, **_CONFLICT},
)
def patch_student(student_id: str, data: StudentPatch, db: DbSession):
    """Only the fields sent are changed; the final combined record is validated before saving."""
    student = _get_or_404(db, student_id)
    try:
        final = StudentUpdate.model_validate(crud.merged_fields(student, data))
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=exc.errors(include_url=False, include_context=False, include_input=False),
        ) from None
    try:
        return crud.replace_student(db, student, final)
    except crud.DuplicateStudentError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None


@router.delete(
    "/{student_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a student",
    responses={**_NOT_FOUND},
)
def delete_student(student_id: str, db: DbSession):
    student = _get_or_404(db, student_id)
    crud.delete_student(db, student)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
