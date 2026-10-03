from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

import models  # noqa: F401

from config import auth_settings
from db.session import engine
from models.base import Base
from routers.auth import router as auth_router
from routers.availability import router as availability_router
from routers.bookings import router as bookings_router
from routers.chapters import router as chapters_router
from routers.courses import router as courses_router
from routers.enrollments import router as enrollments_router
from routers.exercises import router as exercises_router
from routers.lectures import router as lectures_router
from routers.professors import router as professors_router
from routers.students import router as students_router
from routers.submissions import router as submissions_router
from routers.submissions_feed import router as submissions_feed_router
from routers.users import router as users_router
from routers.admin import router as admin_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield


# ---------------------------------------------------------------------------
# Error bodies (item #12): every error is JSON `{detail, code}`, including
# unhandled exceptions (no more plain-text Starlette 500s). A route may raise
# HTTPException(detail={"message": ..., "code": ...}) to set a stable code.
# ---------------------------------------------------------------------------

_STATUS_CODES = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    422: "UNPROCESSABLE_ENTITY",
}


def _register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def _http_exception(request: Request, exc: StarletteHTTPException):
        detail = exc.detail
        if isinstance(detail, dict):
            code = detail.get("code") or _STATUS_CODES.get(exc.status_code, "ERROR")
            message = detail.get("message", detail.get("detail"))
        else:
            code = _STATUS_CODES.get(exc.status_code, "ERROR")
            message = detail
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": message, "code": code},
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={"detail": jsonable_encoder(exc.errors()), "code": "VALIDATION_ERROR"},
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "code": "INTERNAL_ERROR"},
        )


def create_app() -> FastAPI:
    app = FastAPI(
        title="Tutoring Platform API",
        version="1.0.0",
        description="Backend API for tutoring platform",
        lifespan=lifespan,
    )

    _register_error_handlers(app)

    # ---------------------------
    # CORS (adjust for production)
    # ---------------------------
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # change in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ---------------------------
    # Routers
    # ---------------------------
    app.include_router(auth_router,         prefix="/api/v1")
    app.include_router(courses_router,      prefix="/api/v1")
    app.include_router(enrollments_router,  prefix="/api/v1")
    app.include_router(chapters_router,     prefix="/api/v1")
    app.include_router(lectures_router,     prefix="/api/v1")
    app.include_router(exercises_router,    prefix="/api/v1")
    app.include_router(professors_router,   prefix="/api/v1")
    app.include_router(students_router,     prefix="/api/v1")
    app.include_router(availability_router, prefix="/api/v1")
    app.include_router(bookings_router,     prefix="/api/v1")
    app.include_router(submissions_router,  prefix="/api/v1")
    app.include_router(submissions_feed_router, prefix="/api/v1")
    app.include_router(users_router,        prefix="/api/v1")
    app.include_router(admin_router,        prefix="/api/v1")

    # ---------------------------
    # Health Check
    # ---------------------------
    @app.get("/health", tags=["Health"])
    def health_check():
        return {"status": "ok"}

    return app


app = create_app()