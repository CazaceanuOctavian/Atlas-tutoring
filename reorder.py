"""
Shared helper for the transactional bulk-reorder endpoints (item #10).

The client sends the complete, ordered list of ids for a scope; we set each
row's `position` to its index in one transaction. The id set must match the
scope exactly, so a stale or partial list is rejected rather than half-applied.
"""
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def apply_order(
    db: AsyncSession,
    model,
    ids: list[uuid.UUID],
    *,
    parent_field: str | None = None,
    parent_id: uuid.UUID | None = None,
) -> None:
    stmt = select(model)
    if parent_field is not None:
        stmt = stmt.where(getattr(model, parent_field) == parent_id)
    rows = (await db.scalars(stmt)).all()
    by_id = {row.id: row for row in rows}

    if len(ids) != len(set(ids)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ids contains duplicates",
        )
    if set(ids) != set(by_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ids must be exactly the current set of items in this scope",
        )

    for position, _id in enumerate(ids):
        by_id[_id].position = position
    await db.commit()
