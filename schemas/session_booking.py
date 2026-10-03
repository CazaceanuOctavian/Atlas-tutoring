import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from models.session_booking import BookingStatus
from schemas.common import CourseSummary, UserSummary


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


class BookingWithRefs(BookingRead):
    """
    List response that can embed summaries via `?expand=student,professor,course`
    (item #6). Kept off `BookingRead` because these names collide with the ORM
    relationships `SessionBooking.student/professor/course`; see EnrollmentWithRefs.
    """
    student:   Optional[UserSummary]   = None
    professor: Optional[UserSummary]   = None
    course:    Optional[CourseSummary] = None
