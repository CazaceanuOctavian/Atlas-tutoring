import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from schemas.common import UserSummary


class _OrmBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CourseAssignmentCreate(_OrmBase):
    user_id: uuid.UUID


class CourseAssignment(_OrmBase):
    id:          uuid.UUID
    user_id:     uuid.UUID
    course_id:   uuid.UUID
    assigned_at: datetime

    # Professor profile — always embedded on GET /courses/{id}/professors (item #7).
    user: Optional[UserSummary] = None
