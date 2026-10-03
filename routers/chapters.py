import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.session import get_db
from dependencies import admin_only, enrolled_for_chapter, student_only
from models.chapter import Chapter
from models.course import Course
from models.lecture import Lecture
from models.user import User
from pagination import as_page, count_query
from reorder import apply_order
from schemas.chapter import Chapter as ChapterSchema
from schemas.chapter import ChapterCreate, ChapterDetail, ChapterUpdate
from schemas.common import Page, ReorderPayload
from schemas.lecture import Lecture as LectureSchema

router = APIRouter(prefix="/chapters", tags=["chapters"])


@router.get("/", response_model=list[ChapterSchema] | Page[ChapterSchema])
async def list_chapters(
    course_id: uuid.UUID | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    envelope: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(student_only),
):
    """Flat list — no enrollment check since course_id is optional."""
    stmt = select(Chapter).order_by(Chapter.position)
    if course_id:
        stmt = stmt.where(Chapter.course_id == course_id)
    total = await count_query(db, stmt) if envelope else 0
    rows = (await db.scalars(stmt.offset(skip).limit(limit))).all()
    return as_page(rows, total, skip, limit, envelope)


@router.post("/", response_model=ChapterSchema, status_code=status.HTTP_201_CREATED)
async def create_chapter(
    payload: ChapterCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(admin_only),
):
    if not await db.get(Course, payload.course_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Course not found")
    chapter = Chapter(**payload.model_dump())
    db.add(chapter)
    await db.commit()
    await db.refresh(chapter)
    return chapter


@router.get("/{chapter_id}", response_model=ChapterSchema)
async def get_chapter(
    chapter_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(enrolled_for_chapter),
):
    chapter = await db.get(Chapter, chapter_id)
    if not chapter:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Chapter not found")
    return chapter


@router.get("/{chapter_id}/detail", response_model=ChapterDetail)
async def get_chapter_detail(
    chapter_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(enrolled_for_chapter),
):
    result = await db.scalars(
        select(Chapter)
        .where(Chapter.id == chapter_id)
        .options(
            selectinload(Chapter.lectures).selectinload(Lecture.blocks),
            selectinload(Chapter.lectures).selectinload(Lecture.exercises),
        )
    )
    chapter = result.first()
    if not chapter:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Chapter not found")
    return chapter


@router.patch("/{chapter_id}", response_model=ChapterSchema)
async def update_chapter(
    chapter_id: uuid.UUID,
    payload: ChapterUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(admin_only),
):
    chapter = await db.get(Chapter, chapter_id)
    if not chapter:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Chapter not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(chapter, field, value)
    await db.commit()
    await db.refresh(chapter)
    return chapter


@router.delete("/{chapter_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chapter(
    chapter_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(admin_only),
):
    chapter = await db.get(Chapter, chapter_id)
    if not chapter:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Chapter not found")
    await db.delete(chapter)
    await db.commit()


@router.get("/{chapter_id}/lectures", response_model=list[LectureSchema])
async def list_lectures_for_chapter(
    chapter_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(enrolled_for_chapter),
):
    if not await db.get(Chapter, chapter_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Chapter not found")
    result = await db.scalars(
        select(Lecture)
        .where(Lecture.chapter_id == chapter_id)
        .order_by(Lecture.position)
    )
    return result.all()


@router.put("/{chapter_id}/lectures/order", status_code=status.HTTP_204_NO_CONTENT)
async def reorder_lectures(
    chapter_id: uuid.UUID,
    payload: ReorderPayload,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(admin_only),
):
    """Reorder the lectures within a chapter (item #10)."""
    if not await db.get(Chapter, chapter_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Chapter not found")
    await apply_order(db, Lecture, payload.ids, parent_field="chapter_id", parent_id=chapter_id)