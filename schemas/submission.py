import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from models.submission import Language, SubmissionStatus
from schemas.common import ChapterSummary, CourseSummary, ExerciseSummary, LectureSummary, UserSummary


class _OrmBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class SubmissionCreate(_OrmBase):
    code:     str
    language: Language


class TestCaseResult(_OrmBase):
    test_case_id:  uuid.UUID
    order_index:   int
    passed:        bool
    actual_output: Optional[str] = None
    stderr:        Optional[str] = None
    exit_code:     Optional[str] = None
    timed_out:     bool = False


class Submission(_OrmBase):
    id:           uuid.UUID
    exercise_id:  uuid.UUID
    student_id:   uuid.UUID
    code:         str
    language:     Language
    status:       SubmissionStatus
    created_at:   datetime
    stdout:       Optional[str]  = None
    stderr:       Optional[str]  = None
    timed_out:    Optional[bool] = None
    exit_code:    Optional[str]  = None
    passed_count: Optional[int]  = None
    total_count:  Optional[int]  = None
    test_results: list[TestCaseResult] = []


class SubmissionSummary(_OrmBase):
    """
    Lightweight submission row for the global feed (item #3): no code / stdout /
    stderr / test_results, plus embedded context so the console avoids joins.
    """
    id:           uuid.UUID
    exercise_id:  uuid.UUID
    student_id:   uuid.UUID
    language:     Language
    status:       SubmissionStatus
    created_at:   datetime
    passed_count: Optional[int] = None
    total_count:  Optional[int] = None

    exercise: Optional[ExerciseSummary] = None
    lecture:  Optional[LectureSummary]  = None
    chapter:  Optional[ChapterSummary]  = None
    course:   Optional[CourseSummary]   = None
    student:  Optional[UserSummary]     = None


class RunResult(_OrmBase):
    """Result of a dry-run execution (item #11) — same shape, persisted nowhere."""
    status:       SubmissionStatus
    passed_count: Optional[int] = None
    total_count:  Optional[int] = None
    stdout:       Optional[str]  = None
    stderr:       Optional[str]  = None
    timed_out:    Optional[bool] = None
    exit_code:    Optional[str]  = None
    test_results: list[TestCaseResult] = []
