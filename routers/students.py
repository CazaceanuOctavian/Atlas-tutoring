import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from dependencies import professor_only
from models.chapter import Chapter
from models.course import Course
from models.course_assignment import CourseAssignment
from models.enrollment import Enrollment
from models.exercise import Exercise
from models.lecture import Lecture
from models.submission import Submission, SubmissionStatus
from models.user import User, UserRole
from pagination import as_page, count_query
from routers.submissions_feed import feed
from schemas.common import Page
from schemas.submission import SubmissionSummary
from schemas.user import User as UserSchema
from stats import user_stats_map

router = APIRouter(prefix="/students", tags=["students"])


_SORTS = {
    "name":        User.name.asc(),
    "-name":       User.name.desc(),
    "created_at":  User.created_at.asc(),
    "-created_at": User.created_at.desc(),
}


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


async def _decorate_stats(db: AsyncSession, users: list[User]) -> list[UserSchema]:
    items = [UserSchema.model_validate(u) for u in users]
    stat_map = await user_stats_map(db, [u.id for u in users])
    for item in items:
        s = stat_map.get(item.id)
        if s:
            for key, value in s.items():
                setattr(item, key, value)
    return items


@router.get("/", response_model=list[UserSchema] | Page[UserSchema])
async def list_students(
    q:         Optional[str]       = Query(None, description="Case-insensitive match on name or email."),
    course_id: Optional[uuid.UUID] = Query(None, description="Only students enrolled in this course."),
    sort:      str                 = Query("name", description="name | -name | created_at | -created_at"),
    include:   Optional[str]       = Query(None, description="Comma list; 'stats' adds per-student counts."),
    skip:      int                 = Query(0, ge=0),
    limit:     int                 = Query(50, ge=1, le=200),
    envelope:  bool                = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(professor_only),
):
    """
    List students.

    Admins see all students. Professors see only students enrolled in
    courses they are assigned to.
    """
    if current_user.role == UserRole.admin:
        stmt = select(User).where(User.role == UserRole.student)
    else:
        stmt = _students_in_professor_courses(current_user.id)

    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(or_(User.name.ilike(pattern), User.email.ilike(pattern)))

    if course_id:
        enrolled_ids = select(Enrollment.user_id).where(Enrollment.course_id == course_id)
        stmt = stmt.where(User.id.in_(enrolled_ids))

    stmt = stmt.order_by(_SORTS.get(sort, User.name.asc()))

    total = await count_query(db, stmt) if envelope else 0
    users = (await db.scalars(stmt.offset(skip).limit(limit))).all()

    include_set = {s.strip() for s in (include or "").split(",") if s.strip()}
    if "stats" in include_set:
        items = await _decorate_stats(db, list(users))
    else:
        items = list(users)

    return as_page(items, total, skip, limit, envelope)


@router.get("/{student_id}", response_model=UserSchema)
async def get_student(
    student_id: uuid.UUID,
    include: Optional[str] = Query(None),
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

    include_set = {s.strip() for s in (include or "").split(",") if s.strip()}
    if "stats" in include_set:
        return (await _decorate_stats(db, [student]))[0]
    return student


async def _assert_student_visible(db: AsyncSession, current_user: User, student_id: uuid.UUID) -> User:
    """404 if not a student; 403/404 if a professor may not see this student."""
    if current_user.role == UserRole.admin:
        student = await db.get(User, student_id)
    else:
        student = await db.scalar(
            _students_in_professor_courses(current_user.id).where(User.id == student_id)
        )
    if not student or student.role != UserRole.student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    return student


@router.get("/{student_id}/submissions", response_model=list[SubmissionSummary] | Page[SubmissionSummary])
async def list_student_submissions(
    student_id: uuid.UUID,
    course_id:  Optional[uuid.UUID]       = Query(None),
    status_:    Optional[SubmissionStatus] = Query(None, alias="status"),
    sort:       str                        = Query("-created_at"),
    skip:       int                        = Query(0, ge=0),
    limit:      int                        = Query(50, ge=1, le=200),
    envelope:   bool                       = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(professor_only),
):
    """Convenience alias for the submission feed scoped to one student."""
    await _assert_student_visible(db, current_user, student_id)
    items, total = await feed(
        db, current_user,
        student_id=student_id, course_id=course_id, status_=status_,
        sort=sort, skip=skip, limit=limit, need_total=envelope,
    )
    return as_page(items, total, skip, limit, envelope)


@router.get("/{student_id}/progress")
async def student_progress(
    student_id: uuid.UUID,
    course_id: Optional[uuid.UUID] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(professor_only),
):
    """
    Per-exercise best status and attempt count for one student (item #9),
    enabling a solved / attempted / not-started matrix. Optionally scoped to a course.
    """
    await _assert_student_visible(db, current_user, student_id)

    stmt = (
        select(
            Exercise.id,
            Exercise.title,
            Chapter.course_id,
            func.count(Submission.id),
            func.max(Submission.created_at),
            func.bool_or(Submission.status == SubmissionStatus.passed),
        )
        .select_from(Submission)
        .join(Exercise, Exercise.id == Submission.exercise_id)
        .join(Lecture, Lecture.id == Exercise.lecture_id)
        .join(Chapter, Chapter.id == Lecture.chapter_id)
        .where(Submission.student_id == student_id)
        .group_by(Exercise.id, Exercise.title, Chapter.course_id)
    )
    if course_id:
        stmt = stmt.where(Chapter.course_id == course_id)

    rows = (await db.execute(stmt)).all()

    # latest status per exercise (for the non-passed case)
    latest: dict[uuid.UUID, SubmissionStatus] = {}
    latest_rows = await db.execute(
        select(Submission.exercise_id, Submission.status, Submission.created_at)
        .where(Submission.student_id == student_id)
        .order_by(Submission.created_at.desc())
    )
    for ex_id, st, _created in latest_rows.all():
        latest.setdefault(ex_id, st)

    result = []
    for ex_id, title, co_id, attempts, last_at, any_passed in rows:
        best = SubmissionStatus.passed.value if any_passed else (
            latest.get(ex_id).value if latest.get(ex_id) else None
        )
        result.append({
            "exercise_id":    ex_id,
            "exercise_title": title,
            "course_id":      co_id,
            "attempt_count":  attempts,
            "best_status":    best,
            "last_attempt_at": last_at,
        })
    return result
