import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr

from models.user import UserRole
from schemas.common import CourseSummary


class _OrmBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UserBase(_OrmBase):
    name:  str
    email: EmailStr


class UserCreate(UserBase):
    password: str
    role:     UserRole = UserRole.student


class UserUpdate(_OrmBase):
    name:     Optional[str]      = None
    email:    Optional[EmailStr] = None
    password: Optional[str]      = None
    role:     Optional[UserRole] = None


class User(_OrmBase):
    """
    Read schema. `email` is `str` (not `EmailStr`) on purpose: validation
    belongs on input (UserCreate/UserUpdate). A malformed address already in
    the DB must never make a read fail — that was the cause of the /students 500.
    """
    id:         uuid.UUID
    name:       str
    email:      str
    role:       UserRole
    created_at: datetime

    # Per-user stats — populated only when the endpoint is called with
    # `?include=stats` (item #9); null otherwise.
    enrolled_course_count:   Optional[int]      = None
    submission_count:        Optional[int]      = None
    passed_submission_count: Optional[int]      = None
    exercises_solved:        Optional[int]      = None
    last_submission_at:      Optional[datetime] = None

    # Courses the user is a professor of — populated for `role=professor`
    # listings or when `?expand=courses` is passed (item #7); null otherwise.
    courses: Optional[list[CourseSummary]] = None
