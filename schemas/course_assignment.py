import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class _OrmBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CourseAssignmentCreate(_OrmBase):
    user_id: uuid.UUID


class CourseAssignment(_OrmBase):
    id:          uuid.UUID
    user_id:     uuid.UUID
    course_id:   uuid.UUID
    assigned_at: datetime
