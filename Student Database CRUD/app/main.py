"""Application entry point. Run with:  uvicorn app.main:app --reload"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse

from app import database
from app.routers import students

logger = logging.getLogger("students_api")

DESCRIPTION = """
Manage student records with Create, Read, Update and Delete operations.
Data is stored persistently in a local SQLite file.

* **student_id** is chosen by the client: 3-20 letters, digits, `-` or `_`.
* At least one of **email** / **phone** is required. Emails must be unique.
* Dates use ISO format `YYYY-MM-DD`.
* Errors use `{"detail": ...}`; 404 = not found, 409 = duplicate, 422 = invalid data.
"""


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Create the database file and tables automatically on start-up.
    database.init_db(database.engine)
    yield


app = FastAPI(
    title="Students Database CRUD API",
    description=DESCRIPTION,
    version="1.0.0",
    lifespan=lifespan,
)
app.include_router(students.router)


@app.get("/health", tags=["Health"], summary="Health check")
def health():
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def root():
    """Send visitors of the plain address to the interactive API docs."""
    return RedirectResponse(url="/docs")


@app.exception_handler(Exception)
async def unhandled_error(request: Request, exc: Exception):
    """Return a generic 500; log only the exception type, never student data."""
    logger.error("Unhandled %s on %s %s", type(exc).__name__, request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})