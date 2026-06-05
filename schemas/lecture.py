from __future__ import annotations

import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict

from .lecture_block import LectureBlock
from .exercise import Exercise


class _OrmBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class LectureBase(_OrmBase):
    chapter_id: uuid.UUID
    title:      str
    position:   int = 0


class LectureCreate(LectureBase):
    pass


class LectureUpdate(_OrmBase):
    title:    Optional[str] = None
    position: Optional[int] = None


class Lecture(LectureBase):
    id: uuid.UUID


class LectureDetail(Lecture):
    """Lecture with its blocks and exercises pre-loaded."""
    blocks:    list[LectureBlock] = []
    exercises: list[Exercise]     = []