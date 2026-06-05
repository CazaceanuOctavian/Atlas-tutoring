from __future__ import annotations

import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict

from .lecture import LectureDetail


class _OrmBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ChapterBase(_OrmBase):
    course_id: uuid.UUID
    title:     str
    position:  int = 0


class ChapterCreate(ChapterBase):
    pass


class ChapterUpdate(_OrmBase):
    title:    Optional[str] = None
    position: Optional[int] = None


class Chapter(ChapterBase):
    id: uuid.UUID


class ChapterDetail(Chapter):
    """Chapter with its lectures pre-loaded."""
    lectures: list[LectureDetail] = []