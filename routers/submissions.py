import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from dependencies import enrolled_for_exercise, get_current_user
from models.exercise import Exercise
from models.submission import Submission
from models.user import User, UserRole
from schemas.submission import Submission as SubmissionSchema
from schemas.submission import SubmissionCreate

router = APIRouter(prefix="/exercises", tags=["submissions"])


@router.post(
    "/{exercise_id}/submissions",
    response_model=SubmissionSchema,
    status_code=status.HTTP_201_CREATED,
)
async def submit_solution(
    exercise_id: uuid.UUID,
    payload: SubmissionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(enrolled_for_exercise),
):
    """
    Submit a solution for an exercise.
    The student must be enrolled in the course the exercise belongs to.
    """
    if not await db.get(Exercise, exercise_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exercise not found")

    submission = Submission(
        exercise_id=exercise_id,
        student_id=current_user.id,
        code=payload.code,
        language=payload.language,
    )
    db.add(submission)
    await db.commit()
    await db.refresh(submission)
    return submission


@router.get(
    "/{exercise_id}/submissions",
    response_model=list[SubmissionSchema],
)
async def list_submissions(
    exercise_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(enrolled_for_exercise),
):
    """
    List submissions for an exercise.
    - Students see only their own submissions.
    - Admins see all submissions for the exercise.
    """
    if not await db.get(Exercise, exercise_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exercise not found")

    q = select(Submission).where(Submission.exercise_id == exercise_id)

    if current_user.role == UserRole.student:
        q = q.where(Submission.student_id == current_user.id)

    q = q.order_by(Submission.created_at.desc())
    result = await db.scalars(q)
    return result.all()


@router.get(
    "/{exercise_id}/submissions/{submission_id}",
    response_model=SubmissionSchema,
)
async def get_submission(
    exercise_id: uuid.UUID,
    submission_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(enrolled_for_exercise),
):
    """
    Get a specific submission.
    Students can only retrieve their own submissions.
    Admins can retrieve any submission.
    """
    submission = await db.get(Submission, submission_id)

    if not submission or submission.exercise_id != exercise_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")

    if current_user.role == UserRole.student and submission.student_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return submission