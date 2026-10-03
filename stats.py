"""
Aggregate statistics used by the admin console (items #8 and #9).

All helpers are batch-oriented: pass a set of ids and get a map back, so a list
endpoint can decorate every row with one query per metric rather than N queries.
"""
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.chapter import Chapter
from models.course_assignment import CourseAssignment
from models.enrollment import Enrollment
from models.exercise import Exercise
from models.lecture import Lecture
from models.submission import Submission, SubmissionStatus


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Per-user stats (students)
# ---------------------------------------------------------------------------

async def user_stats_map(db: AsyncSession, user_ids: list[uuid.UUID]) -> dict[uuid.UUID, dict]:
    """Map user_id -> stats dict for the given users."""
    if not user_ids:
        return {}

    stats: dict[uuid.UUID, dict] = {
        uid: {
            "enrolled_course_count":   0,
            "submission_count":        0,
            "passed_submission_count": 0,
            "exercises_solved":        0,
            "last_submission_at":      None,
        }
        for uid in user_ids
    }

    enrolled = await db.execute(
        select(Enrollment.user_id, func.count(Enrollment.id))
        .where(Enrollment.user_id.in_(user_ids))
        .group_by(Enrollment.user_id)
    )
    for uid, cnt in enrolled.all():
        stats[uid]["enrolled_course_count"] = cnt

    submissions = await db.execute(
        select(
            Submission.student_id,
            func.count(Submission.id),
            func.count(Submission.id).filter(Submission.status == SubmissionStatus.passed),
            func.max(Submission.created_at),
        )
        .where(Submission.student_id.in_(user_ids))
        .group_by(Submission.student_id)
    )
    for uid, total, passed, last_at in submissions.all():
        stats[uid]["submission_count"] = total
        stats[uid]["passed_submission_count"] = passed
        stats[uid]["last_submission_at"] = last_at

    solved = await db.execute(
        select(Submission.student_id, func.count(distinct(Submission.exercise_id)))
        .where(
            Submission.student_id.in_(user_ids),
            Submission.status == SubmissionStatus.passed,
        )
        .group_by(Submission.student_id)
    )
    for uid, cnt in solved.all():
        stats[uid]["exercises_solved"] = cnt

    return stats


# ---------------------------------------------------------------------------
# Per-course stats
# ---------------------------------------------------------------------------

async def course_stats_map(db: AsyncSession, course_ids: list[uuid.UUID]) -> dict[uuid.UUID, dict]:
    """Map course_id -> stats dict for the given courses."""
    if not course_ids:
        return {}

    stats: dict[uuid.UUID, dict] = {
        cid: {
            "chapter_count":    0,
            "lecture_count":    0,
            "exercise_count":   0,
            "enrolled_count":   0,
            "professor_count":  0,
            "submission_count": 0,
        }
        for cid in course_ids
    }

    chapters = await db.execute(
        select(Chapter.course_id, func.count(Chapter.id))
        .where(Chapter.course_id.in_(course_ids))
        .group_by(Chapter.course_id)
    )
    for cid, cnt in chapters.all():
        stats[cid]["chapter_count"] = cnt

    lectures = await db.execute(
        select(Chapter.course_id, func.count(Lecture.id))
        .join(Lecture, Lecture.chapter_id == Chapter.id)
        .where(Chapter.course_id.in_(course_ids))
        .group_by(Chapter.course_id)
    )
    for cid, cnt in lectures.all():
        stats[cid]["lecture_count"] = cnt

    exercises = await db.execute(
        select(Chapter.course_id, func.count(Exercise.id))
        .select_from(Chapter)
        .join(Lecture, Lecture.chapter_id == Chapter.id)
        .join(Exercise, Exercise.lecture_id == Lecture.id)
        .where(Chapter.course_id.in_(course_ids))
        .group_by(Chapter.course_id)
    )
    for cid, cnt in exercises.all():
        stats[cid]["exercise_count"] = cnt

    enrolled = await db.execute(
        select(Enrollment.course_id, func.count(Enrollment.id))
        .where(Enrollment.course_id.in_(course_ids))
        .group_by(Enrollment.course_id)
    )
    for cid, cnt in enrolled.all():
        stats[cid]["enrolled_count"] = cnt

    professors = await db.execute(
        select(CourseAssignment.course_id, func.count(CourseAssignment.id))
        .where(CourseAssignment.course_id.in_(course_ids))
        .group_by(CourseAssignment.course_id)
    )
    for cid, cnt in professors.all():
        stats[cid]["professor_count"] = cnt

    submissions = await db.execute(
        select(Chapter.course_id, func.count(Submission.id))
        .select_from(Chapter)
        .join(Lecture, Lecture.chapter_id == Chapter.id)
        .join(Exercise, Exercise.lecture_id == Lecture.id)
        .join(Submission, Submission.exercise_id == Exercise.id)
        .where(Chapter.course_id.in_(course_ids))
        .group_by(Chapter.course_id)
    )
    for cid, cnt in submissions.all():
        stats[cid]["submission_count"] = cnt

    return stats


# ---------------------------------------------------------------------------
# Platform-wide stats (admin dashboard)
# ---------------------------------------------------------------------------

async def admin_stats(db: AsyncSession) -> dict:
    from models.course import Course
    from models.user import User, UserRole

    users_by_role = {role.value: 0 for role in UserRole}
    rows = await db.execute(select(User.role, func.count(User.id)).group_by(User.role))
    for role, cnt in rows.all():
        users_by_role[role.value if hasattr(role, "value") else role] = cnt

    async def _count(model) -> int:
        return await db.scalar(select(func.count()).select_from(model)) or 0

    by_status = {s.value: 0 for s in SubmissionStatus}
    rows = await db.execute(
        select(Submission.status, func.count(Submission.id)).group_by(Submission.status)
    )
    for st, cnt in rows.all():
        by_status[st.value if hasattr(st, "value") else st] = cnt

    week_ago = _utcnow() - timedelta(days=7)
    last_7_days = await db.scalar(
        select(func.count(Submission.id)).where(Submission.created_at >= week_ago)
    ) or 0
    active_students_7d = await db.scalar(
        select(func.count(distinct(Submission.student_id))).where(
            Submission.created_at >= week_ago
        )
    ) or 0

    return {
        "users":       users_by_role,
        "courses":     await _count(Course),
        "chapters":    await _count(Chapter),
        "lectures":    await _count(Lecture),
        "exercises":   await _count(Exercise),
        "enrollments": await _count(Enrollment),
        "submissions": {
            "total":       sum(by_status.values()),
            "last_7_days": last_7_days,
            "by_status":   by_status,
        },
        "active_students_7d": active_students_7d,
        "generated_at":       _utcnow(),
    }
