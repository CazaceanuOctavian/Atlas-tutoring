import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.session import get_db
from dependencies import get_current_user
from models.chapter import Chapter
from models.course import Course
from models.course_assignment import CourseAssignment
from models.exercise import Exercise
from models.lecture import Lecture
from models.submission import Language, Submission, SubmissionStatus
from models.user import User, UserRole
from pagination import as_page, count_query
from schemas.common import (
    ChapterSummary,
    CourseSummary,
    ExerciseSummary,
    LectureSummary,
    Page,
    UserSummary,
)
from schemas.submission import Submission as SubmissionSchema
from schemas.submission import SubmissionSummary

router = APIRouter(prefix="/submissions", tags=["submissions-feed"])


def _summary(row) -> SubmissionSummary:
    sub, ex, lec, ch, co, student = row
    return SubmissionSummary(
        id=sub.id,
        exercise_id=sub.exercise_id,
        student_id=sub.student_id,
        language=sub.language,
        status=sub.status,
        created_at=sub.created_at,
        passed_count=sub.passed_count,
        total_count=sub.total_count,
        exercise=ExerciseSummary.model_validate(ex),
        lecture=LectureSummary.model_validate(lec),
        chapter=ChapterSummary.model_validate(ch),
        course=CourseSummary.model_validate(co),
        student=UserSummary.model_validate(student),
    )


async def feed(
    db: AsyncSession,
    viewer: User,
    *,
    student_id: Optional[uuid.UUID] = None,
    course_id: Optional[uuid.UUID] = None,
    exercise_id: Optional[uuid.UUID] = None,
    status_: Optional[SubmissionStatus] = None,
    language: Optional[Language] = None,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    sort: str = "-created_at",
    skip: int = 0,
    limit: int = 50,
    need_total: bool = False,
):
    """
    Shared, role-scoped submission feed query. Returns (summaries, total).
    `total` is only computed when `need_total` is set.
    """
    stmt = (
        select(Submission, Exercise, Lecture, Chapter, Course, User)
        .join(Exercise, Exercise.id == Submission.exercise_id)
        .join(Lecture, Lecture.id == Exercise.lecture_id)
        .join(Chapter, Chapter.id == Lecture.chapter_id)
        .join(Course, Course.id == Chapter.course_id)
        .join(User, User.id == Submission.student_id)
    )

    # ---- role scoping ----
    if viewer.role == UserRole.student:
        stmt = stmt.where(Submission.student_id == viewer.id)
    elif viewer.role == UserRole.professor:
        prof_courses = select(CourseAssignment.course_id).where(
            CourseAssignment.user_id == viewer.id
        )
        stmt = stmt.where(Chapter.course_id.in_(prof_courses))

    # ---- filters ----
    if student_id is not None:
        stmt = stmt.where(Submission.student_id == student_id)
    if course_id is not None:
        stmt = stmt.where(Chapter.course_id == course_id)
    if exercise_id is not None:
        stmt = stmt.where(Submission.exercise_id == exercise_id)
    if status_ is not None:
        stmt = stmt.where(Submission.status == status_)
    if language is not None:
        stmt = stmt.where(Submission.language == language)
    if since is not None:
        stmt = stmt.where(Submission.created_at >= since)
    if until is not None:
        stmt = stmt.where(Submission.created_at <= until)

    order = Submission.created_at.asc() if sort == "created_at" else Submission.created_at.desc()
    stmt = stmt.order_by(order)

    total = await count_query(db, stmt) if need_total else 0
    rows = (await db.execute(stmt.offset(skip).limit(limit))).all()
    return [_summary(r) for r in rows], total


@router.get("/", response_model=list[SubmissionSummary] | Page[SubmissionSummary])
async def list_submissions(
    student_id:  Optional[uuid.UUID]       = Query(None),
    course_id:   Optional[uuid.UUID]       = Query(None),
    exercise_id: Optional[uuid.UUID]       = Query(None),
    status_:     Optional[SubmissionStatus] = Query(None, alias="status"),
    language:    Optional[Language]        = Query(None),
    since:       Optional[datetime]        = Query(None),
    until:       Optional[datetime]        = Query(None),
    sort:        str                       = Query("-created_at", description="-created_at | created_at"),
    skip:        int                       = Query(0, ge=0),
    limit:       int                       = Query(50, ge=1, le=200),
    envelope:    bool                      = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Global, filterable submission feed (summary rows).
    Admin: all. Professor: their assigned courses. Student: forced to own.
    """
    items, total = await feed(
        db, current_user,
        student_id=student_id, course_id=course_id, exercise_id=exercise_id,
        status_=status_, language=language, since=since, until=until,
        sort=sort, skip=skip, limit=limit, need_total=envelope,
    )
    return as_page(items, total, skip, limit, envelope)


@router.get("/{submission_id}", response_model=SubmissionSchema)
async def get_submission(
    submission_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Full submission record by id, without needing the exercise id in the path."""
    submission = await db.scalar(
        select(Submission)
        .where(Submission.id == submission_id)
        .options(selectinload(Submission.test_results))
    )
    if not submission:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")

    if current_user.role == UserRole.student:
        if submission.student_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    elif current_user.role == UserRole.professor:
        exercise = await db.get(Exercise, submission.exercise_id)
        lecture = await db.get(Lecture, exercise.lecture_id)
        chapter = await db.get(Chapter, lecture.chapter_id)
        assigned = await db.scalar(
            select(CourseAssignment).where(
                CourseAssignment.user_id == current_user.id,
                CourseAssignment.course_id == chapter.course_id,
            )
        )
        if not assigned:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return submission
