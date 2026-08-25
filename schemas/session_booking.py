import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

from models.session_booking import BookingStatus


class _OrmBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class BookingCreate(_OrmBase):
    availability_id: uuid.UUID
    start_time:      datetime
    end_time:        datetime

    @field_validator("end_time")
    @classmethod
    def end_after_start(cls, v: datetime, info) -> datetime:
        start = info.data.get("start_time")
        if start and v <= start:
            raise ValueError("end_time must be after start_time")
        return v


class BookingStatusUpdate(_OrmBase):
    status: BookingStatus


class BookingRead(_OrmBase):
    id:              uuid.UUID
    student_id:      uuid.UUID
    professor_id:    uuid.UUID
    course_id:       uuid.UUID
    availability_id: uuid.UUID
    start_time:      datetime
    end_time:        datetime
    status:          BookingStatus
    created_at:      datetime
