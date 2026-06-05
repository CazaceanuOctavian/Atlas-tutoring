import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.session import get_db


from models.chapter import Chapter
from models.course import Course
from schemas.chapter import Chapter as ChapterSchema
from schemas.course import Course as CourseSchema
from schemas.course import CourseCreate, CourseDetail, CourseUpdate

router = APIRouter(prefix="/courses", tags=["courses"])

# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

@router.get("/", response_model=list[CourseSchema])
async def list_courses(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    result = await db.scalars(select(Course).offset(skip).limit(limit))
    return result.all()


@router.post("/", response_model=CourseSchema, status_code=status.HTTP_201_CREATED)
async def create_course(payload: CourseCreate, db: AsyncSession = Depends(get_db)):
    course = Course(**payload.model_dump())
    db.add(course)
    await db.commit()
    await db.refresh(course)
    return course


@router.get("/{course_id}", response_model=CourseSchema)
async def get_course(course_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    course = await db.get(Course, course_id)
    if not course:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Course not found")
    return course


@router.get("/{course_id}/detail", response_model=CourseDetail)
async def get_course_detail(course_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Return the full course tree: chapters → lectures → blocks & exercises."""
    result = await db.scalars(
        select(Course)
        .where(Course.id == course_id)
        .options(
            selectinload(Course.chapters).selectinload(Chapter.lectures)
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
async def delete_course(course_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    course = await db.get(Course, course_id)
    if not course:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Course not found")
    await db.delete(course)
    await db.commit()


# ---------------------------------------------------------------------------
# Nested — chapters
# ---------------------------------------------------------------------------

@router.get("/{course_id}/chapters", response_model=list[ChapterSchema])
async def list_chapters_for_course(course_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    if not await db.get(Course, course_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Course not found")
    result = await db.scalars(
        select(Chapter)
        .where(Chapter.course_id == course_id)
        .order_by(Chapter.position)
    )
    return result.all()