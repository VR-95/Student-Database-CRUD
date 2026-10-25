"""Pydantic request/response schemas and all input validation rules.

Rules (documented in README):
* student_id : 3-20 chars, letters/digits/hyphen/underscore, supplied by the client,
               case-sensitive, immutable after creation.
* name       : required, 1-100 chars after trimming, must contain a letter.
* date_of_birth : required, strict ``YYYY-MM-DD``, a real date, not in the future.
* email      : optional, valid address, stored lower-case, unique across students.
* phone      : optional, 7-15 digits, may contain + ( ) - and spaces.
* At least one of email / phone is required.
* course / address : optional, trimmed, blank becomes null, length limited.
* enrollment_date : optional, strict ``YYYY-MM-DD``, not before date_of_birth.
"""

import re
from datetime import date
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

STUDENT_ID_PATTERN = r"^[A-Za-z0-9_-]{3,20}$"
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_PHONE_CHARS = re.compile(r"^\+?[0-9 ()\-]+$")


def parse_iso_date(value: Any) -> date:
    """Accept only a ``YYYY-MM-DD`` string (or a date object); never timestamps."""
    if isinstance(value, date):
        return value
    if not isinstance(value, str) or not _ISO_DATE.match(value.strip()):
        raise ValueError("date must be in YYYY-MM-DD format")
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        raise ValueError("date is not a real calendar date") from None


def clean_text(value: Any) -> Any:
    """Trim whitespace of strings; leave other types for Pydantic to reject."""
    return value.strip() if isinstance(value, str) else value


def clean_phone(value: str) -> str:
    value = value.strip()
    digits = re.sub(r"\D", "", value)
    if not _PHONE_CHARS.match(value) or not 7 <= len(digits) <= 15:
        raise ValueError("phone must contain 7-15 digits and only + ( ) - or spaces")
    return value


class _StudentFields(BaseModel):
    """Field rules shared by create, replace (PUT) and partial update (PATCH)."""

    # Unknown fields (for example student_id in PUT/PATCH) are rejected, never ignored.
    model_config = ConfigDict(extra="forbid")

    @field_validator("name", check_fields=False)
    @classmethod
    def _check_name(cls, value: str | None) -> str | None:
        if value is None:
            raise ValueError("name cannot be null")
        value = value.strip()
        if not value or not any(ch.isalpha() for ch in value):
            raise ValueError("name must not be blank and must contain a letter")
        return value

    @field_validator("date_of_birth", "enrollment_date", mode="before", check_fields=False)
    @classmethod
    def _parse_dates(cls, value: Any) -> Any:
        return None if value is None else parse_iso_date(value)

    @field_validator("date_of_birth", check_fields=False)
    @classmethod
    def _dob_not_future(cls, value: date | None) -> date | None:
        if value is None:
            raise ValueError("date_of_birth cannot be null")
        if value > date.today():
            raise ValueError("date_of_birth cannot be in the future")
        return value

    @field_validator("email", mode="before", check_fields=False)
    @classmethod
    def _strip_email(cls, value: Any) -> Any:
        return clean_text(value)

    @field_validator("email", check_fields=False)
    @classmethod
    def _lower_email(cls, value: str | None) -> str | None:
        return value.lower() if value else None

    @field_validator("phone", check_fields=False)
    @classmethod
    def _check_phone(cls, value: str | None) -> str | None:
        return clean_phone(value) if value else None

    @field_validator("course", "address", mode="before", check_fields=False)
    @classmethod
    def _trim_text(cls, value: Any) -> Any:
        return clean_text(value)

    @field_validator("course", "address", check_fields=False)
    @classmethod
    def _blank_to_none(cls, value: str | None) -> str | None:
        return value or None

    @model_validator(mode="after")
    def _cross_field_rules(self) -> "_StudentFields":
        dob = getattr(self, "date_of_birth", None)
        enrolled = getattr(self, "enrollment_date", None)
        if dob and enrolled and enrolled < dob:
            raise ValueError("enrollment_date cannot be before date_of_birth")
        return self


# --- Request schemas -------------------------------------------------------

_EXAMPLE = {
    "name": "Aarav Sharma",
    "date_of_birth": "2004-05-17",
    "email": "aarav.sharma@example.com",
    "phone": "+91 98765 43210",
    "course": "Computer Science",
    "address": "12 Example Street, Mumbai",
    "enrollment_date": "2022-08-01",
}


class StudentUpdate(_StudentFields):
    """Full set of editable fields (used by PUT). student_id is NOT editable."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [_EXAMPLE]})

    name: str = Field(max_length=100)
    date_of_birth: date
    email: EmailStr | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, max_length=20)
    course: str | None = Field(default=None, max_length=100)
    address: str | None = Field(default=None, max_length=255)
    enrollment_date: date | None = None

    @model_validator(mode="after")
    def _need_contact(self) -> "StudentUpdate":
        if not (self.email or self.phone):
            raise ValueError("at least one contact method (email or phone) is required")
        return self


class StudentCreate(StudentUpdate):
    """Request body for POST /students: editable fields plus the client-chosen ID."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"examples": [{"student_id": "S2024-001", **_EXAMPLE}]},
    )

    student_id: str = Field(pattern=STUDENT_ID_PATTERN, examples=["S2024-001"])


class StudentPatch(_StudentFields):
    """Partial update (PATCH): only the fields sent are changed."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"examples": [{"course": "Data Science", "phone": "9876543210"}]},
    )

    name: str | None = Field(default=None, max_length=100)
    date_of_birth: date | None = None
    email: EmailStr | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, max_length=20)
    course: str | None = Field(default=None, max_length=100)
    address: str | None = Field(default=None, max_length=255)
    enrollment_date: date | None = None

    @model_validator(mode="after")
    def _not_empty(self) -> "StudentPatch":
        if not self.model_fields_set:
            raise ValueError("at least one field must be provided")
        return self


# --- Response schema -------------------------------------------------------


class StudentRead(BaseModel):
    """Student as returned by the API (dates are serialised as YYYY-MM-DD)."""

    model_config = ConfigDict(from_attributes=True)

    student_id: str
    name: str
    date_of_birth: date
    email: str | None
    phone: str | None
    course: str | None
    address: str | None
    enrollment_date: date | None