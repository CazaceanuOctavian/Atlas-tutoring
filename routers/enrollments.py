import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.session import get_db
from dependencies import admin_only, get_current_user, student_only
from models.course import Course
from models.enrollment import Enrollment
from models.user import User, UserRole
from pagination import as_page, count_query
from schemas.common import CourseSummary, Page, UserSummary
from schemas.enrollment import Enrollment as EnrollmentSchema
from schemas.enrollment import EnrollmentCreate

router = APIRouter(prefix="/enrollments", tags=["enrollments"])


def _parse_expand(expand: Optional[str]) -> set[str]:
    return {s.strip() for s in (expand or "").split(",") if s.strip()}


def _serialize_enrollments(enrollments, expand: set[str]) -> list[EnrollmentSchema]:
    items = []
    for enr in enrollments:
        item = EnrollmentSchema.model_validate(enr)
        if "course" in expand and enr.course is not None:
            item.course = CourseSummary.model_validate(enr.course)
        if "user" in expand and enr.user is not None:
            item.user = UserSummary.model_validate(enr.user)
        items.append(item)
    return items


@router.post("/", response_model=EnrollmentSchema, status_code=status.HTTP_201_CREATED)
async def enroll(
    payload: EnrollmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Admins can enroll any user in any course.
    Students can only enroll themselves.
    """
    if current_user.role == UserRole.student and payload.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Students can only enroll themselves",
        )

    if not await db.get(Course, payload.course_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    if not await db.get(User, payload.user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    enrollment = Enrollment(**payload.model_dump())
    db.add(enrollment)
    try:
        await db.commit()
        await db.refresh(enrollment)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already enrolled in this course",
        )
    return enrollment

@router.delete("/{enrollment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unenroll(
    enrollment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Admins can unenroll anyone.
    Students can only unenroll themselves.
    """
    enrollment = await db.get(Enrollment, enrollment_id)
    if not enrollment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enrollment not found")

    if current_user.role == UserRole.student and enrollment.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Students can only unenroll themselves",
        )

    await db.delete(enrollment)
    await db.commit()

@router.get("/", response_model=list[EnrollmentSchema] | Page[EnrollmentSchema])
async def list_enrollments(
    user_id:   Optional[uuid.UUID] = Query(None),
    course_id: Optional[uuid.UUID] = Query(None),
    expand:    Optional[str]       = Query(None, description="Comma list: course, user."),
    skip:      int                 = Query(0, ge=0),
    limit:     int                 = Query(50, ge=1, le=200),
    envelope:  bool                = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Admins see all enrollments (filterable).
    Students see only their own.
    """
    expand_set = _parse_expand(expand)
    stmt = select(Enrollment)
    if current_user.role == UserRole.student:
        stmt = stmt.where(Enrollment.user_id == current_user.id)
    if user_id is not None:
        stmt = stmt.where(Enrollment.user_id == user_id)
    if course_id is not None:
        stmt = stmt.where(Enrollment.course_id == course_id)

    if "course" in expand_set:
        stmt = stmt.options(selectinload(Enrollment.course))
    if "user" in expand_set:
        stmt = stmt.options(selectinload(Enrollment.user))

    total = await count_query(db, stmt) if envelope else 0
    rows = (await db.scalars(stmt.offset(skip).limit(limit))).all()
    items = _serialize_enrollments(rows, expand_set)
    return as_page(items, total, skip, limit, envelope)


@router.get("/me", response_model=list[EnrollmentSchema])
async def my_enrollments(
    expand: Optional[str] = Query(None, description="Comma list: course, user."),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(student_only),
):
    """Return the current student's enrollments."""
    expand_set = _parse_expand(expand)
    stmt = select(Enrollment).where(Enrollment.user_id == current_user.id)
    if "course" in expand_set:
        stmt = stmt.options(selectinload(Enrollment.course))
    if "user" in expand_set:
        stmt = stmt.options(selectinload(Enrollment.user))
    rows = (await db.scalars(stmt)).all()
    return _serialize_enrollments(rows, expand_set)