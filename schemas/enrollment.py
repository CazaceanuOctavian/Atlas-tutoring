import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


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