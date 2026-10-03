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


class EnrollmentWithRefs(Enrollment):
    """
    List response that can embed summaries via `?expand=course,user` (item #6).

    The embed fields live on this subclass — not on `Enrollment` — because their
    names collide with the ORM relationships `Enrollment.course` / `.user`.
    If they were on the base schema, `from_attributes` serialization of a bare
    ORM object (e.g. from POST /enrollments) would lazy-load those relationships
    in async context and raise MissingGreenlet. The list endpoints build this
    subclass from the base's scalar data and set the refs explicitly.
    """
    course: Optional[CourseSummary] = None
    user:   Optional[UserSummary]   = None