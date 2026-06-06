import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict


class _OrmBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class LectureBlockBase(_OrmBase):
    lecture_id: uuid.UUID
    markdown:   str
    position:   int = 0


class LectureBlockCreate(LectureBlockBase):
    pass


class LectureBlockUpdate(_OrmBase):
    markdown:  Optional[str] = None
    position:  Optional[int] = None


class LectureBlock(LectureBlockBase):
    id: uuid.UUID