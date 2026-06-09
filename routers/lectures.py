import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.session import get_db
from dependencies import admin_only, enrolled_for_lecture, student_only
from models.chapter import Chapter
from models.exercise import Exercise
from models.lecture import Lecture
from models.lecture_block import LectureBlock
from models.user import User
from schemas.exercise import Exercise as ExerciseSchema
from schemas.lecture import Lecture as LectureSchema
from schemas.lecture import LectureCreate, LectureDetail, LectureUpdate
from schemas.lecture_block import LectureBlock as LectureBlockSchema
from schemas.lecture_block import LectureBlockCreate, LectureBlockUpdate

router = APIRouter(prefix="/lectures", tags=["lectures"])


@router.get("/", response_model=list[LectureSchema])
async def list_lectures(
    chapter_id: uuid.UUID | None = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(student_only),
):
    q = select(Lecture).order_by(Lecture.position)
    if chapter_id:
        q = q.where(Lecture.chapter_id == chapter_id)
    result = await db.scalars(q.offset(skip).limit(limit))
    return result.all()


@router.post("/", response_model=LectureSchema, status_code=status.HTTP_201_CREATED)
async def create_lecture(
    payload: LectureCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(admin_only),
):
    if not await db.get(Chapter, payload.chapter_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Chapter not found")
    lecture = Lecture(**payload.model_dump())
    db.add(lecture)
    await db.commit()
    await db.refresh(lecture)
    return lecture


@router.get("/{lecture_id}", response_model=LectureSchema)
async def get_lecture(
    lecture_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(enrolled_for_lecture),
):
    lecture = await db.get(Lecture, lecture_id)
    if not lecture:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Lecture not found")
    return lecture


@router.get("/{lecture_id}/detail", response_model=LectureDetail)
async def get_lecture_detail(
    lecture_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(enrolled_for_lecture),
):
    result = await db.scalars(
        select(Lecture)
        .where(Lecture.id == lecture_id)
        .options(
            selectinload(Lecture.blocks),
            selectinload(Lecture.exercises),
        )
    )
    lecture = result.first()
    if not lecture:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Lecture not found")
    return lecture


@router.patch("/{lecture_id}", response_model=LectureSchema)
async def update_lecture(
    lecture_id: uuid.UUID,
    payload: LectureUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(admin_only),
):
    lecture = await db.get(Lecture, lecture_id)
    if not lecture:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Lecture not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(lecture, field, value)
    await db.commit()
    await db.refresh(lecture)
    return lecture


@router.delete("/{lecture_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lecture(
    lecture_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(admin_only),
):
    lecture = await db.get(Lecture, lecture_id)
    if not lecture:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Lecture not found")
    await db.delete(lecture)
    await db.commit()


# ---------------------------------------------------------------------------
# Nested — blocks
# ---------------------------------------------------------------------------

@router.get("/{lecture_id}/blocks", response_model=list[LectureBlockSchema])
async def list_blocks(
    lecture_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(enrolled_for_lecture),
):
    if not await db.get(Lecture, lecture_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Lecture not found")
    result = await db.scalars(
        select(LectureBlock)
        .where(LectureBlock.lecture_id == lecture_id)
        .order_by(LectureBlock.position)
    )
    return result.all()


@router.post("/{lecture_id}/blocks", response_model=LectureBlockSchema, status_code=status.HTTP_201_CREATED)
async def create_block(
    lecture_id: uuid.UUID,
    payload: LectureBlockCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(admin_only),
):
    if not await db.get(Lecture, lecture_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Lecture not found")
    block = LectureBlock(**payload.model_dump())
    db.add(block)
    await db.commit()
    await db.refresh(block)
    return block


@router.patch("/{lecture_id}/blocks/{block_id}", response_model=LectureBlockSchema)
async def update_block(
    lecture_id: uuid.UUID,
    block_id: uuid.UUID,
    payload: LectureBlockUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(admin_only),
):
    block = await db.get(LectureBlock, block_id)
    if not block or block.lecture_id != lecture_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Block not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(block, field, value)
    await db.commit()
    await db.refresh(block)
    return block


@router.delete("/{lecture_id}/blocks/{block_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_block(
    lecture_id: uuid.UUID,
    block_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(admin_only),
):
    block = await db.get(LectureBlock, block_id)
    if not block or block.lecture_id != lecture_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Block not found")
    await db.delete(block)
    await db.commit()


# ---------------------------------------------------------------------------
# Nested — exercises
# ---------------------------------------------------------------------------

@router.get("/{lecture_id}/exercises", response_model=list[ExerciseSchema])
async def list_exercises_for_lecture(
    lecture_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(enrolled_for_lecture),
):
    if not await db.get(Lecture, lecture_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Lecture not found")
    result = await db.scalars(
        select(Exercise)
        .where(Exercise.lecture_id == lecture_id)
        .order_by(Exercise.position)
    )
    return result.all()