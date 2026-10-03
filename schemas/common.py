"""
Shared schema building blocks:

- `Page[T]` — the opt-in pagination envelope (`?envelope=1`) carrying the
  total row count alongside the current page.
- Small `*Summary` schemas — embedded in responses (via `?expand=`) so the
  admin console can render names/titles without extra round-trips.
"""
import uuid
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict


class _OrmBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """Envelope returned when a list endpoint is called with `?envelope=1`."""
    items: list[T]
    total: int
    skip:  int
    limit: int


class ReorderPayload(BaseModel):
    """Body for the bulk reorder endpoints (item #10): the full set of ids
    in their desired order."""
    ids: list[uuid.UUID]


# ---------------------------------------------------------------------------
# Embedded display summaries — just enough to render a label.
# ---------------------------------------------------------------------------

class UserSummary(_OrmBase):
    id:    uuid.UUID
    name:  str
    email: str


class CourseSummary(_OrmBase):
    id:    uuid.UUID
    title: str


class ChapterSummary(_OrmBase):
    id:    uuid.UUID
    title: str


class LectureSummary(_OrmBase):
    id:    uuid.UUID
    title: str


class ExerciseSummary(_OrmBase):
    id:    uuid.UUID
    title: str
