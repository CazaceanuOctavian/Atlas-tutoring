import uuid
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.session import get_db
from dependencies import admin_only, enrolled_for_course, get_current_user, student_only
from models.chapter import Chapter
from models.course import Course
from models.course_assignment import CourseAssignment
from models.lecture import Lecture
from models.user import User
from pagination import as_page, count_query
from reorder import apply_order
from schemas.chapter import Chapter as ChapterSchema
from schemas.common import Page, ReorderPayload
from schemas.course import Course as CourseSchema
from schemas.course import CourseCreate, CourseDetail, CourseUpdate
from stats import course_stats_map

router = APIRouter(prefix="/courses", tags=["courses"])


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

@router.get("/", response_model=list[CourseSchema] | Page[CourseSchema])
async def list_courses(
    q:            Optional[str]       = Query(None, description="Case-insensitive match on title."),
    professor_id: Optional[uuid.UUID] = Query(None, description="Courses taught by this professor."),
    include:      Optional[str]       = Query(None, description="Comma list; 'stats' adds per-course counts."),
    skip:         int                 = Query(0, ge=0),
    limit:        int                 = Query(100, ge=1, le=200),
    envelope:     bool                = Query(False),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(student_only),
):
    """Any authenticated user can see the course catalogue."""
    stmt = select(Course).order_by(Course.position)
    if q:
        stmt = stmt.where(Course.title.ilike(f"%{q}%"))
    if professor_id is not None:
        taught = select(CourseAssignment.course_id).where(CourseAssignment.user_id == professor_id)
        stmt = stmt.where(Course.id.in_(taught))

    total = await count_query(db, stmt) if envelope else 0
    courses = (await db.scalars(stmt.offset(skip).limit(limit))).all()

    include_set = {s.strip() for s in (include or "").split(",") if s.strip()}
    if "stats" in include_set:
        stat_map = await course_stats_map(db, [c.id for c in courses])
        items = []
        for c in courses:
            item = CourseSchema.model_validate(c)
            s = stat_map.get(c.id)
            if s:
                for key, value in s.items():
                    setattr(item, key, value)
            items.append(item)
    else:
        items = list(courses)

    return as_page(items, total, skip, limit, envelope)


@router.post("/", response_model=CourseSchema, status_code=status.HTTP_201_CREATED)
async def create_course(
    payload: CourseCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(admin_only),
):
    course = Course(**payload.model_dump())
    db.add(course)
    await db.commit()
    await db.refresh(course)
    return course


@router.get("/{course_id}", response_model=CourseSchema)
async def get_course(
    course_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(enrolled_for_course),
):
    course = await db.get(Course, course_id)
    if not course:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Course not found")
    return course


@router.get("/{course_id}/detail", response_model=CourseDetail)
async def get_course_detail(
    course_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(enrolled_for_course),
):
    result = await db.scalars(
        select(Course)
        .where(Course.id == course_id)
        .options(
            selectinload(Course.chapters).selectinload(Chapter.lectures).selectinload(Lecture.blocks),
            selectinload(Course.chapters).selectinload(Chapter.lectures).selectinload(Lecture.exercises),
        )
    )
    course = result.first()
    if not course:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Course not found")
    return course


@router.patch("/{course_id}", response_model=CourseSchema)
async def update_course(
    course_id: uuid.UUID,
    payload: CourseUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(admin_only),
):
    course = await db.get(Course, course_id)
    if not course:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Course not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(course, field, value)
    await db.commit()
    await db.refresh(course)
    return course


@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_course(
    course_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(admin_only),
):
    course = await db.get(Course, course_id)
    if not course:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Course not found")
    await db.delete(course)
    await db.commit()


@router.get("/{course_id}/chapters", response_model=list[ChapterSchema])
async def list_chapters_for_course(
    course_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(enrolled_for_course),
):
    if not await db.get(Course, course_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Course not found")
    result = await db.scalars(
        select(Chapter)
        .where(Chapter.course_id == course_id)
        .order_by(Chapter.position)
    )
    return result.all()


# ---------------------------------------------------------------------------
# Bulk reorder (item #10) — transactional
# ---------------------------------------------------------------------------

@router.put("/order", status_code=status.HTTP_204_NO_CONTENT)
async def reorder_courses(
    payload: ReorderPayload,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(admin_only),
):
    """Set the position of every course from the given ordered id list."""
    await apply_order(db, Course, payload.ids)


@router.put("/{course_id}/chapters/order", status_code=status.HTTP_204_NO_CONTENT)
async def reorder_chapters(
    course_id: uuid.UUID,
    payload: ReorderPayload,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(admin_only),
):
    """Reorder the chapters within a course."""
    if not await db.get(Course, course_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Course not found")
    await apply_order(db, Chapter, payload.ids, parent_field="course_id", parent_id=course_id)