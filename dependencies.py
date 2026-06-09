"""
Central place to wire auth dependencies to the real get_db.
Import from here in all routers instead of from jwt directly.
"""
import uuid

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from jwt import make_get_current_user, require_admin, require_student
from models.chapter import Chapter
from models.enrollment import Enrollment
from models.exercise import Exercise
from models.lecture import Lecture
from models.user import User, UserRole

# ---------------------------------------------------------------------------
# Auth dependencies
# ---------------------------------------------------------------------------

get_current_user = make_get_current_user(get_db)

admin_only   = require_admin(get_current_user)
student_only = require_student(get_current_user)


# ---------------------------------------------------------------------------
# Enrollment guard helpers
# ---------------------------------------------------------------------------

async def _check_enrollment(user: User, course_id: uuid.UUID, db: AsyncSession) -> None:
    """Raises 403 if the student is not enrolled in the given course."""
    if user.role == UserRole.admin:
        return
    result = await db.scalars(
        select(Enrollment).where(
            Enrollment.user_id   == user.id,
            Enrollment.course_id == course_id,
        )
    )
    if not result.first():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not enrolled in this course",
        )


# ---------------------------------------------------------------------------
# One dependency per resource type — FastAPI resolves path params by name.
# ---------------------------------------------------------------------------

async def enrolled_for_course(
    course_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> User:
    """Use on any route that has a `course_id` path parameter."""
    await _check_enrollment(current_user, course_id, db)
    return current_user


async def enrolled_for_chapter(
    chapter_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> User:
    """Use on any route that has a `chapter_id` path parameter."""
    if current_user.role == UserRole.admin:
        return current_user
    chapter = await db.get(Chapter, chapter_id)
    if not chapter:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found")
    await _check_enrollment(current_user, chapter.course_id, db)
    return current_user


async def enrolled_for_lecture(
    lecture_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> User:
    """Use on any route that has a `lecture_id` path parameter."""
    if current_user.role == UserRole.admin:
        return current_user
    lecture = await db.get(Lecture, lecture_id)
    if not lecture:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lecture not found")
    chapter = await db.get(Chapter, lecture.chapter_id)
    await _check_enrollment(current_user, chapter.course_id, db)
    return current_user


async def enrolled_for_exercise(
    exercise_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> User:
    """Use on any route that has an `exercise_id` path parameter."""
    if current_user.role == UserRole.admin:
        return current_user
    exercise = await db.get(Exercise, exercise_id)
    if not exercise:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exercise not found")
    lecture = await db.get(Lecture, exercise.lecture_id)
    chapter = await db.get(Chapter, lecture.chapter_id)
    await _check_enrollment(current_user, chapter.course_id, db)
    return current_user