import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from models.submission import Language


class _OrmBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class SubmissionCreate(_OrmBase):
    code:     str
    language: Language


class Submission(_OrmBase):
    id:          uuid.UUID
    exercise_id: uuid.UUID
    student_id:  uuid.UUID
    code:        str
    language:    Language
    created_at:  datetime