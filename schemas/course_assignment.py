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


class CourseAssignmentWithUser(CourseAssignment):
    """
    GET /courses/{id}/professors embeds the professor profile (item #7).
    Kept off the base schema because `user` collides with the ORM relationship
    `CourseAssignment.user`; see EnrollmentWithRefs for the rationale.
    """
    user: Optional[UserSummary] = None
