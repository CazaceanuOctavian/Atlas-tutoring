import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict


class _OrmBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TestCaseBase(_OrmBase):
    exercise_id:     uuid.UUID
    expected_output: str
    input:           Optional[str] = None
    description:     Optional[str] = None


class TestCaseCreate(TestCaseBase):
    pass


class TestCaseUpdate(_OrmBase):
    input:           Optional[str] = None
    expected_output: Optional[str] = None
    description:     Optional[str] = None


class TestCase(TestCaseBase):
    id: uuid.UUID