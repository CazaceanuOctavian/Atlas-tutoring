import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db

from models.exercise import Exercise
from models.exercise_block import ExerciseBlock
from models.lecture import Lecture
from models.test_case import TestCase
from schemas.exercise import Exercise as ExerciseSchema
from schemas.exercise import ExerciseCreate, ExerciseUpdate
from schemas.exercise_block import ExerciseBlock as ExerciseBlockSchema
from schemas.exercise_block import ExerciseBlockCreate, ExerciseBlockUpdate
from schemas.test_case import TestCase as TestCaseSchema
from schemas.test_case import TestCaseCreate, TestCaseUpdate

router = APIRouter(prefix="/exercises", tags=["exercises"])


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

@router.get("/", response_model=list[ExerciseSchema])
async def list_exercises(
    lecture_id: uuid.UUID | None = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """List exercises, optionally filtered by lecture."""
    q = select(Exercise).order_by(Exercise.position)
    if lecture_id:
        q = q.where(Exercise.lecture_id == lecture_id)
    result = await db.scalars(q.offset(skip).limit(limit))
    return result.all()


@router.post("/", response_model=ExerciseSchema, status_code=status.HTTP_201_CREATED)
async def create_exercise(payload: ExerciseCreate, db: AsyncSession = Depends(get_db)):
    if not await db.get(Lecture, payload.lecture_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Lecture not found")
    exercise = Exercise(**payload.model_dump())
    db.add(exercise)
    await db.commit()
    await db.refresh(exercise)
    return exercise


@router.get("/{exercise_id}", response_model=ExerciseSchema)
async def get_exercise(exercise_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    exercise = await db.get(Exercise, exercise_id)
    if not exercise:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Exercise not found")
    return exercise


@router.patch("/{exercise_id}", response_model=ExerciseSchema)
async def update_exercise(
    exercise_id: uuid.UUID,
    payload: ExerciseUpdate,
    db: AsyncSession = Depends(get_db),
):
    exercise = await db.get(Exercise, exercise_id)
    if not exercise:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Exercise not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(exercise, field, value)
    await db.commit()
    await db.refresh(exercise)
    return exercise


@router.delete("/{exercise_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_exercise(exercise_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    exercise = await db.get(Exercise, exercise_id)
    if not exercise:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Exercise not found")
    await db.delete(exercise)
    await db.commit()


# ---------------------------------------------------------------------------
# Nested — blocks
# ---------------------------------------------------------------------------

@router.get("/{exercise_id}/blocks", response_model=list[ExerciseBlockSchema])
async def list_blocks(exercise_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    if not await db.get(Exercise, exercise_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Exercise not found")
    result = await db.scalars(
        select(ExerciseBlock)
        .where(ExerciseBlock.exercise_id == exercise_id)
        .order_by(ExerciseBlock.position)
    )
    return result.all()


@router.post(
    "/{exercise_id}/blocks",
    response_model=ExerciseBlockSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_block(
    exercise_id: uuid.UUID,
    payload: ExerciseBlockCreate,
    db: AsyncSession = Depends(get_db),
):
    if not await db.get(Exercise, exercise_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Exercise not found")
    block = ExerciseBlock(**payload.model_dump())
    db.add(block)
    await db.commit()
    await db.refresh(block)
    return block


@router.patch("/{exercise_id}/blocks/{block_id}", response_model=ExerciseBlockSchema)
async def update_block(
    exercise_id: uuid.UUID,
    block_id: uuid.UUID,
    payload: ExerciseBlockUpdate,
    db: AsyncSession = Depends(get_db),
):
    block = await db.get(ExerciseBlock, block_id)
    if not block or block.exercise_id != exercise_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Block not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(block, field, value)
    await db.commit()
    await db.refresh(block)
    return block


@router.delete(
    "/{exercise_id}/blocks/{block_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_block(
    exercise_id: uuid.UUID,
    block_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    block = await db.get(ExerciseBlock, block_id)
    if not block or block.exercise_id != exercise_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Block not found")
    await db.delete(block)
    await db.commit()


# ---------------------------------------------------------------------------
# Nested — test cases
# ---------------------------------------------------------------------------

@router.get("/{exercise_id}/test-cases", response_model=list[TestCaseSchema])
async def list_test_cases(exercise_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    if not await db.get(Exercise, exercise_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Exercise not found")
    result = await db.scalars(
        select(TestCase).where(TestCase.exercise_id == exercise_id)
    )
    return result.all()


@router.post(
    "/{exercise_id}/test-cases",
    response_model=TestCaseSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_test_case(
    exercise_id: uuid.UUID,
    payload: TestCaseCreate,
    db: AsyncSession = Depends(get_db),
):
    if not await db.get(Exercise, exercise_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Exercise not found")
    test_case = TestCase(**payload.model_dump())
    db.add(test_case)
    await db.commit()
    await db.refresh(test_case)
    return test_case


@router.patch(
    "/{exercise_id}/test-cases/{test_case_id}",
    response_model=TestCaseSchema,
)
async def update_test_case(
    exercise_id: uuid.UUID,
    test_case_id: uuid.UUID,
    payload: TestCaseUpdate,
    db: AsyncSession = Depends(get_db),
):
    test_case = await db.get(TestCase, test_case_id)
    if not test_case or test_case.exercise_id != exercise_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Test case not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(test_case, field, value)
    await db.commit()
    await db.refresh(test_case)
    return test_case


@router.delete(
    "/{exercise_id}/test-cases/{test_case_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_test_case(
    exercise_id: uuid.UUID,
    test_case_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    test_case = await db.get(TestCase, test_case_id)
    if not test_case or test_case.exercise_id != exercise_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Test case not found")
    await db.delete(test_case)
    await db.commit()