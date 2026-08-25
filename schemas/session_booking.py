import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from models.session_booking import BookingStatus


class _OrmBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class BookingCreate(_OrmBase):
    availability_id: uuid.UUID


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
