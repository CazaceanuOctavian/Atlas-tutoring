import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from config import auth_settings
from db.session import get_db
from dependencies import enrolled_for_exercise, get_current_user, professor_only
from models.exercise import Exercise
from models.submission import Submission, SubmissionStatus
from models.submission_test_result import SubmissionTestResult
from models.test_case import TestCase
from models.user import User, UserRole
from schemas.submission import Submission as SubmissionSchema
from schemas.submission import RunResult, SubmissionCreate

router = APIRouter(prefix="/exercises", tags=["submissions"])

EXECUTOR_BASE_URL = auth_settings.runner_url.rsplit("/run", 1)[0]


async def _run_single(
    code: str,
    language: str,
    stdin: str,
    timeout: int = 10,
) -> dict:
    async with httpx.AsyncClient(timeout=float(timeout + 30)) as client:
        response = await client.post(
            f"{EXECUTOR_BASE_URL}/run-batch",
            json={
                "code": code,
                "language": language,
                "stdin_list": [stdin],
                "timeout": timeout,
            },
        )
    response.raise_for_status()
    return response.json()["results"][0]


def _with_test_results(q):
    return q.options(selectinload(Submission.test_results))


async def _grade(code: str, language_value: str, test_cases: list) -> dict:
    """
    Run `code` against the exercise's test cases (or once, if there are none)
    and return a structured grading result. Pure: it talks to the runner and
    builds a dict, but touches neither the DB nor any Submission.

    Returns keys: status, passed_count, total_count, stdout, stderr, timed_out,
    exit_code, results (list of per-test-case dicts).
    """
    out: dict = {
        "status": SubmissionStatus.passed,
        "passed_count": None,
        "total_count": None,
        "stdout": None,
        "stderr": None,
        "timed_out": None,
        "exit_code": None,
        "results": [],
    }

    try:
        if not test_cases:
            run_result = await _run_single(code=code, language=language_value, stdin="")
            out["stdout"]    = run_result.get("stdout", "")
            out["stderr"]    = run_result.get("stderr", "")
            out["exit_code"] = run_result.get("exit_code")
            out["timed_out"] = run_result.get("timed_out", False)
            if out["timed_out"]:
                out["status"] = SubmissionStatus.timeout
            elif str(out["exit_code"]) == "0":
                out["status"] = SubmissionStatus.passed
            else:
                out["status"] = SubmissionStatus.failed
            return out

        passed_count = 0
        final_status = SubmissionStatus.passed
        last_run: dict | None = None

        for index, tc in enumerate(test_cases):
            run_result = await _run_single(code=code, language=language_value, stdin=tc.input or "")
            last_run = run_result

            timed_out = run_result.get("timed_out", False)
            exit_code = run_result.get("exit_code")
            stdout    = run_result.get("stdout", "") or ""
            stderr    = run_result.get("stderr", "") or ""
            ok = (not timed_out) and str(exit_code) == "0" and stdout.strip() == (tc.expected_output or "").strip()
            passed_count += int(ok)

            out["results"].append({
                "test_case_id": tc.id,
                "order_index":  index,
                "passed":       ok,
                "actual_output": stdout,
                "stderr":       stderr,
                "exit_code":    str(exit_code) if exit_code is not None else None,
                "timed_out":    timed_out,
            })

            if not ok:
                if timed_out:
                    final_status = SubmissionStatus.timeout
                elif str(exit_code) != "0":
                    final_status = SubmissionStatus.error
                else:
                    final_status = SubmissionStatus.failed
                break  # stop — no further executions

        total = len(test_cases)
        out["passed_count"] = passed_count
        out["total_count"]  = total
        out["status"] = SubmissionStatus.passed if passed_count == total else final_status
        if last_run:
            out["stdout"]    = last_run.get("stdout", "")
            out["stderr"]    = last_run.get("stderr", "")
            out["exit_code"] = last_run.get("exit_code")
            out["timed_out"] = last_run.get("timed_out", False)
        return out

    except httpx.TimeoutException:
        out["status"]    = SubmissionStatus.timeout
        out["stderr"]    = "Execution service timed out"
        out["timed_out"] = True
        return out
    except Exception as exc:
        out["status"] = SubmissionStatus.error
        out["stderr"] = f"Execution service error: {exc}"
        return out


async def _test_cases_for(db: AsyncSession, exercise_id: uuid.UUID) -> list:
    result = await db.scalars(select(TestCase).where(TestCase.exercise_id == exercise_id))
    return result.all()


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

    test_cases = await _test_cases_for(db, exercise_id)
    graded = await _grade(payload.code, payload.language.value, test_cases)

    submission.status       = graded["status"]
    submission.passed_count = graded["passed_count"]
    submission.total_count  = graded["total_count"]
    submission.stdout       = graded["stdout"]
    submission.stderr       = graded["stderr"]
    submission.exit_code    = graded["exit_code"]
    submission.timed_out    = graded["timed_out"]

    for r in graded["results"]:
        db.add(SubmissionTestResult(submission_id=submission.id, **r))

    await db.commit()

    refreshed = await db.scalar(
        _with_test_results(
            select(Submission).where(Submission.id == submission.id)
        )
    )
    return refreshed


@router.post("/{exercise_id}/run", response_model=RunResult)
async def dry_run(
    exercise_id: uuid.UUID,
    payload: SubmissionCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(professor_only),
):
    """
    Dry-run code against the exercise's test cases (admin/professor), returning
    the same grading shape as a submission but persisting nothing (item #11).
    """
    if not await db.get(Exercise, exercise_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exercise not found")

    test_cases = await _test_cases_for(db, exercise_id)
    graded = await _grade(payload.code, payload.language.value, test_cases)
    return RunResult(
        status=graded["status"],
        passed_count=graded["passed_count"],
        total_count=graded["total_count"],
        stdout=graded["stdout"],
        stderr=graded["stderr"],
        timed_out=graded["timed_out"],
        exit_code=graded["exit_code"],
        test_results=graded["results"],
    )


@router.get(
    "/{exercise_id}/submissions",
    response_model=list[SubmissionSchema],
)
async def list_submissions(
    exercise_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(enrolled_for_exercise),
):
    if not await db.get(Exercise, exercise_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exercise not found")

    q = select(Submission).where(Submission.exercise_id == exercise_id)

    if current_user.role == UserRole.student:
        q = q.where(Submission.student_id == current_user.id)

    q = _with_test_results(q).order_by(Submission.created_at.desc())
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
    submission = await db.scalar(
        _with_test_results(
            select(Submission).where(Submission.id == submission_id)
        )
    )

    if not submission or submission.exercise_id != exercise_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")

    if current_user.role == UserRole.student and submission.student_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return submission
