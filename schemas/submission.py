import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from models.submission import Language, SubmissionStatus


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
