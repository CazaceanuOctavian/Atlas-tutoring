import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from dependencies import admin_only, get_current_user, student_only
from models.course import Course
from models.enrollment import Enrollment
from models.user import User, UserRole
from schemas.enrollment import Enrollment as EnrollmentSchema
from schemas.enrollment import EnrollmentCreate

router = APIRouter(prefix="/enrollments", tags=["enrollments"])


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

@router.get("/", response_model=list[EnrollmentSchema])
async def list_enrollments(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Admins see all enrollments.
    Students see only their own.
    """
    q = select(Enrollment)
    if current_user.role == UserRole.student:
        q = q.where(Enrollment.user_id == current_user.id)
    result = await db.scalars(q)
    return result.all()


@router.get("/me", response_model=list[EnrollmentSchema])
async def my_enrollments(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(student_only),
):
    """Return the current student's enrollments."""
    result = await db.scalars(
        select(Enrollment).where(Enrollment.user_id == current_user.id)
    )
    return result.all()