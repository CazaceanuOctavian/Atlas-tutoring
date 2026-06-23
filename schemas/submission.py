import enum
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from models.submission import Language


class _OrmBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class SubmissionCreate(_OrmBase):
    code:     str
    language: Language

class SubmissionStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    passed = "passed"
    failed = "failed"
    error = "error"
    timeout = "timeout"


class ExecutionResult(_OrmBase):
    stdout:    Optional[str]  = None
    stderr:    Optional[str]  = None
    timed_out: Optional[bool] = None
    exit_code: Optional[str]  = None


class Submission(_OrmBase):
    id:          uuid.UUID
    exercise_id: uuid.UUID
    student_id:  uuid.UUID
    code:        str
    language:    Language
    created_at:  datetime

    stdout:      Optional[str] = None
    stderr:      Optional[str] = None
    timed_out:   Optional[bool] = None
    exit_code:   Optional[str] = None

    status:      SubmissionStatus

class SubmissionCreate(_OrmBase):
    code: str
    language: Language