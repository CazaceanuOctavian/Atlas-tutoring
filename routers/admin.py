from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from dependencies import admin_only
from models.user import User
from stats import admin_stats

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/stats")
async def get_admin_stats(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(admin_only),
):
    """Platform-wide dashboard aggregate (admin only)."""
    return await admin_stats(db)
