import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from dependencies import admin_only, enrolled_for_course
from models.course import Course
from models.course_assignment import CourseAssignment
from models.user import User, UserRole
from schemas.course_assignment import CourseAssignment as CourseAssignmentSchema
from schemas.course_assignment import CourseAssignmentCreate

router = APIRouter(prefix="/courses", tags=["professors"])


@router.post(
    "/{course_id}/professors",
    response_model=CourseAssignmentSchema,
    status_code=status.HTTP_201_CREATED,
)
async def assign_professor(
    course_id: uuid.UUID,
    payload: CourseAssignmentCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(admin_only),
):
    """Assign a professor to a course (admin only)."""
    if not await db.get(Course, course_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    professor = await db.get(User, payload.user_id)
    if not professor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if professor.role != UserRole.professor:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not a professor",
        )

    assignment = CourseAssignment(user_id=payload.user_id, course_id=course_id)
    db.add(assignment)
    try:
        await db.commit()
        await db.refresh(assignment)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Professor is already assigned to this course",
        )
    return assignment


@router.delete(
    "/{course_id}/professors/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_professor(
    course_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(admin_only),
):
    """Remove a professor from a course (admin only)."""
    result = await db.scalars(
        select(CourseAssignment).where(
            CourseAssignment.user_id   == user_id,
            CourseAssignment.course_id == course_id,
        )
    )
    assignment = result.first()
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assignment not found",
        )
    await db.delete(assignment)
    await db.commit()


@router.get(
    "/{course_id}/professors",
    response_model=list[CourseAssignmentSchema],
)
async def list_professors(
    course_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(enrolled_for_course),
):
    """List all professors assigned to a course."""
    if not await db.get(Course, course_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    result = await db.scalars(
        select(CourseAssignment).where(CourseAssignment.course_id == course_id)
    )
    return result.all()
