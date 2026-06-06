from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from .chapter import ChapterDetail


class _OrmBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CourseBase(_OrmBase):
    title:       str
    description: Optional[str] = None


class CourseCreate(CourseBase):
    pass


class CourseUpdate(_OrmBase):
    title:       Optional[str] = None
    description: Optional[str] = None


class Course(CourseBase):
    id:         uuid.UUID
    created_at: datetime


class CourseDetail(Course):
    """Course with full chapter -> lecture -> block tree."""
    chapters: list[ChapterDetail] = []