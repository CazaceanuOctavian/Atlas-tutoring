import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict


class _OrmBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ExerciseBase(_OrmBase):
    lecture_id: uuid.UUID
    title:      str
    position:   int = 0


class ExerciseCreate(ExerciseBase):
    pass


class ExerciseUpdate(_OrmBase):
    title:    Optional[str] = None
    position: Optional[int] = None


class Exercise(ExerciseBase):
    id: uuid.UUID