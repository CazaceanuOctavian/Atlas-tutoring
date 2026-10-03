"""
Helpers for the opt-in pagination envelope (`?envelope=1`).

List endpoints keep returning a bare array by default so existing clients are
unaffected; when `envelope=1` is passed they return `{items, total, skip, limit}`
instead. `response_model` on those endpoints is `list[X] | Page[X]`.
"""
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession

from schemas.common import Page


async def count_query(db: AsyncSession, stmt) -> int:
    """
    Total row count for a SELECT, ignoring its ordering/offset/limit.

    Uses `with_only_columns(count())` rather than wrapping the statement in a
    subquery: the feed selects several entities that each have an `id` column,
    and a derived table with duplicate column names is rejected by Postgres.
    Safe here because none of our list statements group or fan out (all joins
    are many-to-one), so `count(*)` equals the row count.
    """
    count_stmt = stmt.with_only_columns(func.count(), maintain_column_froms=True).order_by(None)
    return await db.scalar(count_stmt) or 0


def as_page(rows, total: int, skip: int, limit: int, envelope: bool):
    """Return the bare rows, or wrap them in a Page when envelope is requested."""
    if envelope:
        return Page(items=list(rows), total=total, skip=skip, limit=limit)
    return list(rows)
