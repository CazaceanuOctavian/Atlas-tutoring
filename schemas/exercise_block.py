import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict


class _OrmBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ExerciseBlockBase(_OrmBase):
    exercise_id: uuid.UUID
    markdown:    str
    position:    int = 0


class ExerciseBlockCreate(ExerciseBlockBase):
    pass


class ExerciseBlockUpdate(_OrmBase):
    markdown:  Optional[str] = None
    position:  Optional[int] = None


class ExerciseBlock(ExerciseBlockBase):
    id: uuid.UUID