import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from schemas.common import CourseSummary, UserSummary


class _OrmBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class EnrollmentBase(_OrmBase):
    user_id:   uuid.UUID
    course_id: uuid.UUID


class EnrollmentCreate(EnrollmentBase):
    pass


class Enrollment(EnrollmentBase):
    id:          uuid.UUID
    enrolled_at: datetime

    # Populated when the endpoint is called with `?expand=course,user` (item #6).
    course: Optional[CourseSummary] = None
    user:   Optional[UserSummary]   = None