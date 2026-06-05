from fastapi import FastAPI

from routers.courses import router as courses_router
from routers.exercises import router as exercises_router
from routers.lectures import router as lectures_router


def register_routers(app: FastAPI) -> None:
    """Mount all routers onto the FastAPI application."""
    app.include_router(courses_router)
    app.include_router(lectures_router)
    app.include_router(exercises_router)