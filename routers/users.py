import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from dependencies import admin_only
from models.course import Course
from models.course_assignment import CourseAssignment
from models.user import User, UserRole
from pagination import as_page, count_query
from schemas.common import CourseSummary, Page
from schemas.user import User as UserSchema
from schemas.user import UserUpdate
from stats import user_stats_map

router = APIRouter(prefix="/users", tags=["users"])


def _parse_roles(role: Optional[list[str]]) -> list[UserRole]:
    """Accept role repeated and/or comma-separated: ?role=professor,admin&role=student."""
    if not role:
        return []
    out: list[UserRole] = []
    for raw in role:
        for part in raw.split(","):
            part = part.strip()
            if not part:
                continue
            try:
                out.append(UserRole(part))
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Unknown role: {part}",
                )
    return out


_SORTS = {
    "name":        User.name.asc(),
    "-name":       User.name.desc(),
    "created_at":  User.created_at.asc(),
    "-created_at": User.created_at.desc(),
}


async def _courses_map(db: AsyncSession, professor_ids: list[uuid.UUID]) -> dict[uuid.UUID, list]:
    """Map professor user_id -> [Course, ...] they are assigned to."""
    if not professor_ids:
        return {}
    rows = await db.execute(
        select(CourseAssignment.user_id, Course)
        .join(Course, Course.id == CourseAssignment.course_id)
        .where(CourseAssignment.user_id.in_(professor_ids))
    )
    out: dict[uuid.UUID, list] = {}
    for uid, course in rows.all():
        out.setdefault(uid, []).append(course)
    return out


async def _serialize(
    db: AsyncSession,
    users: list[User],
    include_stats: bool,
    expand_courses: bool,
) -> list[UserSchema]:
    """Turn ORM users into schemas, optionally decorated with stats / courses."""
    items = [UserSchema.model_validate(u) for u in users]

    if include_stats:
        ids = [u.id for u in users]
        stat_map = await user_stats_map(db, ids)
        for item in items:
            s = stat_map.get(item.id)
            if s:
                for key, value in s.items():
                    setattr(item, key, value)

    if expand_courses:
        prof_ids = [u.id for u in users if u.role == UserRole.professor]
        cmap = await _courses_map(db, prof_ids)
        for item in items:
            if item.role == UserRole.professor:
                item.courses = [CourseSummary.model_validate(c) for c in cmap.get(item.id, [])]

    return items


@router.get("/", response_model=list[UserSchema] | Page[UserSchema])
async def list_users(
    role:     Optional[list[str]] = Query(None, description="Filter by role; repeatable or comma-separated."),
    q:        Optional[str]       = Query(None, description="Case-insensitive match on name or email."),
    sort:     str                 = Query("name", description="name | -name | created_at | -created_at"),
    include:  Optional[str]       = Query(None, description="Comma list; 'stats' adds per-user counts."),
    expand:   Optional[str]       = Query(None, description="Comma list; 'courses' adds a professor's courses."),
    skip:     int                 = Query(0, ge=0),
    limit:    int                 = Query(50, ge=1, le=200),
    envelope: bool                = Query(False, description="Wrap response as {items,total,skip,limit}."),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(admin_only),
):
    """Directory of all users (admin only)."""
    stmt = select(User)

    roles = _parse_roles(role)
    if roles:
        stmt = stmt.where(User.role.in_(roles))

    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(or_(User.name.ilike(pattern), User.email.ilike(pattern)))

    stmt = stmt.order_by(_SORTS.get(sort, User.name.asc()))

    total = await count_query(db, stmt) if envelope else 0
    users = (await db.scalars(stmt.offset(skip).limit(limit))).all()

    include_set = {s.strip() for s in (include or "").split(",") if s.strip()}
    expand_set  = {s.strip() for s in (expand or "").split(",") if s.strip()}
    items = await _serialize(db, list(users), "stats" in include_set, "courses" in expand_set)

    return as_page(items, total, skip, limit, envelope)


@router.get("/{user_id}", response_model=UserSchema)
async def get_user(
    user_id: uuid.UUID,
    include: Optional[str] = Query(None),
    expand:  Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(admin_only),
):
    """Retrieve any user by id (admin only)."""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    include_set = {s.strip() for s in (include or "").split(",") if s.strip()}
    expand_set  = {s.strip() for s in (expand or "").split(",") if s.strip()}
    items = await _serialize(db, [user], "stats" in include_set, "courses" in expand_set)
    return items[0]


@router.patch("/{user_id}", response_model=UserSchema)
async def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(admin_only),
):
    """
    Update a user (admin only). Primarily to promote a user to professor/admin,
    since everyone starts as a student after Google sign-in.
    """
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    updates = payload.model_dump(exclude_unset=True)
    password = updates.pop("password", None)
    if password is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password changes are not supported via this endpoint",
        )
    for field, value in updates.items():
        setattr(user, field, value)

    await db.commit()
    await db.refresh(user)
    return user
