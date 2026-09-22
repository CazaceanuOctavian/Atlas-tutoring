import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from dependencies import professor_only
from models.course_assignment import CourseAssignment
from models.enrollment import Enrollment
from models.user import User, UserRole
from schemas.user import User as UserSchema

router = APIRouter(prefix="/students", tags=["students"])


def _students_in_professor_courses(professor_id: uuid.UUID):
    """Subquery-scoped select of students enrolled in the professor's courses."""
    professor_courses = (
        select(CourseAssignment.course_id)
        .where(CourseAssignment.user_id == professor_id)
    )
    enrolled_student_ids = (
        select(Enrollment.user_id)
        .where(Enrollment.course_id.in_(professor_courses))
    )
    return select(User).where(
        User.role == UserRole.student,
        User.id.in_(enrolled_student_ids),
    )


@router.get("/", response_model=list[UserSchema])
async def list_students(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(professor_only),
):
    """
    List students.

    Admins see all students. Professors see only students enrolled in
    courses they are assigned to.
    """
    if current_user.role == UserRole.admin:
        q = select(User).where(User.role == UserRole.student)
    else:
        q = _students_in_professor_courses(current_user.id)
    result = await db.scalars(q)
    return result.all()


@router.get("/{student_id}", response_model=UserSchema)
async def get_student(
    student_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(professor_only),
):
    """
    Retrieve a single student's data by id.

    Admins can retrieve any student. Professors can only retrieve students
    enrolled in a course they are assigned to.
    """
    if current_user.role == UserRole.admin:
        student = await db.get(User, student_id)
    else:
        student = await db.scalar(
            _students_in_professor_courses(current_user.id).where(User.id == student_id)
        )

    if not student or student.role != UserRole.student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found",
        )
    return student
