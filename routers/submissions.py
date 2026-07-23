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
from models.test_case import TestCase
from models.user import User, UserRole
from schemas.submission import Submission as SubmissionSchema
from schemas.submission import SubmissionCreate

router = APIRouter(prefix="/exercises", tags=["submissions"])

EXECUTOR_BASE_URL = auth_settings.runner_url.rsplit("/run", 1)[0]


async def _run_remote_batch(
    code: str,
    language: str,
    stdin_list: list[str],
    timeout: int = 10,
) -> list[dict]:
    """
    Call the remote executor's /run-batch endpoint.
    The remote runner writes + compiles the code ONCE, then executes it
    once per stdin entry against the SAME container, and only restarts
    the container after the entire batch finishes.
    """
    request_timeout = timeout * max(len(stdin_list), 1) + 30.0
    async with httpx.AsyncClient(timeout=request_timeout) as client:
        response = await client.post(
            f"{EXECUTOR_BASE_URL}/run-batch",
            json={
                "code": code,
                "language": language,
                "stdin_list": stdin_list,
                "timeout": timeout,
            },
        )
    response.raise_for_status()
    return response.json()["results"]


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

    Flow:
    1. Save submission as QUEUED.
    2. Fetch all test cases for the exercise.
    3. Send ONE batch request to the remote executor — code is written
       and compiled (C++) exactly once, then run once per test case's
       `input` (as stdin), all against the SAME container. The container
       is only restarted after the whole submission finishes.
    4. Compare each run's stdout against the matching expected_output.
    5. Store the aggregate result + passed_testcases percentage.
    """
    exercise = await db.get(Exercise, exercise_id)
    if not exercise:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exercise not found")

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

    submission.status = SubmissionStatus.running
    await db.commit()

    result = await db.scalars(
        select(TestCase).where(TestCase.exercise_id == exercise_id)
    )
    test_cases = result.all()

    try:
        if not test_cases:
            # No test cases — single run, no stdin, no grading
            run_results = await _run_remote_batch(
                code=payload.code,
                language=payload.language.value,
                stdin_list=[""],
            )
            run_result = run_results[0]

            submission.stdout            = run_result.get("stdout", "")
            submission.stderr            = run_result.get("stderr", "")
            submission.exit_code         = run_result.get("exit_code")
            submission.timed_out         = run_result.get("timed_out", False)
            submission.passed_testcases  = None

            if submission.timed_out:
                submission.status = SubmissionStatus.timeout
            elif str(submission.exit_code) == "0":
                submission.status = SubmissionStatus.passed
            else:
                submission.status = SubmissionStatus.failed

        else:
            stdin_list = [tc.input or "" for tc in test_cases]
            run_results = await _run_remote_batch(
                code=payload.code,
                language=payload.language.value,
                stdin_list=stdin_list,
            )

            passed_count  = 0
            any_timed_out = False
            any_error     = False
            last = run_results[-1]   # report the last run's raw output on the submission

            for tc, run_result in zip(test_cases, run_results):
                stdout    = run_result.get("stdout", "") or ""
                exit_code = run_result.get("exit_code")
                timed_out = run_result.get("timed_out", False)

                if timed_out:
                    any_timed_out = True
                    continue
                if str(exit_code) != "0":
                    any_error = True
                    continue
                if stdout.strip() == (tc.expected_output or "").strip():
                    passed_count += 1

            total = len(test_cases)
            submission.passed_testcases = round((passed_count / total) * 100, 2)
            submission.stdout    = last.get("stdout", "")
            submission.stderr    = last.get("stderr", "")
            submission.exit_code = last.get("exit_code")
            submission.timed_out = last.get("timed_out", False)

            if any_timed_out:
                submission.status = SubmissionStatus.timeout
            elif passed_count == total:
                submission.status = SubmissionStatus.passed
            elif any_error:
                submission.status = SubmissionStatus.error
            else:
                submission.status = SubmissionStatus.failed

    except httpx.TimeoutException:
        submission.status    = SubmissionStatus.timeout
        submission.stderr    = "Execution service timed out"
        submission.timed_out = True

    except Exception as exc:
        submission.status = SubmissionStatus.error
        submission.stderr  = f"Execution service error: {exc}"

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