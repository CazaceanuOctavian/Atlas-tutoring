import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import auth_settings
from db.session import get_db
from dependencies import enrolled_for_exercise, get_current_user
from models.exercise import Exercise
from models.submission import Submission, SubmissionStatus
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
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(enrolled_for_exercise),
):
    """
    Submit a solution for an exercise.
    - Saves submission as QUEUED
    - Executes remotely
    - Updates status + results
    """

    if not await db.get(Exercise, exercise_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exercise not found",
        )

    # 1. Create submission (QUEUED)
    submission = Submission(
        exercise_id=exercise_id,
        student_id=current_user.id,
        code=payload.code,
        language=payload.language,
        status=SubmissionStatus.queued,
    )

    db.add(submission)
    await db.commit()
    await db.refresh(submission)

    # 2. Mark as RUNNING before execution
    submission.status = SubmissionStatus.running
    await db.commit()

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                auth_settings.runner_url,
                json={
                    "code": payload.code,
                    "language": payload.language.value,
                },
            )

        response.raise_for_status()
        result = response.json()

        submission.stdout = result.get("stdout", "")
        submission.stderr = result.get("stderr", "")
        submission.exit_code = result.get("exit_code")
        submission.timed_out = result.get("timed_out", False)

        # 3. Final status based on result
        if submission.timed_out:
            submission.status = SubmissionStatus.timeout
        elif str(submission.exit_code) == "0":
            submission.status = SubmissionStatus.passed
        else:
            submission.status = SubmissionStatus.failed

    except httpx.TimeoutException:
        submission.status = SubmissionStatus.timeout
        submission.stderr = "Execution service timed out"
        submission.timed_out = True

    except Exception as exc:
        submission.status = SubmissionStatus.error
        submission.stderr = f"Execution service error: {str(exc)}"

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
    Get a specific submission by ID.
    Students can only retrieve their own submissions.
    """
    submission = await db.get(Submission, submission_id)

    if not submission or submission.exercise_id != exercise_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")

    if current_user.role == UserRole.student and submission.student_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return submission