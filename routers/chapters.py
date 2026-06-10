import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.session import get_db
from dependencies import admin_only, enrolled_for_chapter, student_only
from models.chapter import Chapter
from models.course import Course
from models.lecture import Lecture
from models.user import User
from schemas.chapter import Chapter as ChapterSchema
from schemas.chapter import ChapterCreate, ChapterDetail, ChapterUpdate
from schemas.lecture import Lecture as LectureSchema

router = APIRouter(prefix="/chapters", tags=["chapters"])


@router.get("/", response_model=list[ChapterSchema])
async def list_chapters(
    course_id: uuid.UUID | None = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(student_only),
):
    """Flat list — no enrollment check since course_id is optional."""
    q = select(Chapter).order_by(Chapter.position)
    if course_id:
        q = q.where(Chapter.course_id == course_id)
    result = await db.scalars(q.offset(skip).limit(limit))
    return result.all()


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