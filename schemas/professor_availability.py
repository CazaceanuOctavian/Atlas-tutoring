import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class _OrmBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class AvailabilityCreate(_OrmBase):
    course_id:    uuid.UUID
    start_time:   datetime
    end_time:     datetime
    max_students: int = 1

    @field_validator("max_students")
    @classmethod
    def at_least_one(cls, v: int) -> int:
        if v < 1:
            raise ValueError("max_students must be at least 1")
        return v

    @field_validator("end_time")
    @classmethod
    def end_after_start(cls, v: datetime, info) -> datetime:
        start = info.data.get("start_time")
        if start and v <= start:
            raise ValueError("end_time must be after start_time")
        return v


class AvailabilityUpdate(_OrmBase):
    start_time:   Optional[datetime] = None
    end_time:     Optional[datetime] = None
    max_students: Optional[int]      = None

    @field_validator("max_students")
    @classmethod
    def at_least_one(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 1:
            raise ValueError("max_students must be at least 1")
        return v


class AvailabilityRead(_OrmBase):
    id:           uuid.UUID
    professor_id: uuid.UUID
    course_id:    uuid.UUID
    start_time:   datetime
    end_time:     datetime
    max_students: int
    booked_count: int
    created_at:   datetime
