from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
from routers.submissions import router as submissions_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Tutoring Platform API",
        version="1.0.0",
        description="Backend API for tutoring platform",
        lifespan=lifespan,
    )

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
    app.include_router(availability_router, prefix="/api/v1")
    app.include_router(bookings_router,     prefix="/api/v1")
    app.include_router(submissions_router,  prefix="/api/v1")

    # ---------------------------
    # Health Check
    # ---------------------------
    @app.get("/health", tags=["Health"])
    def health_check():
        return {"status": "ok"}

    return app


app = create_app()