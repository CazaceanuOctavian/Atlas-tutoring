import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from dependencies import get_current_user, professor_only
from models.course_assignment import CourseAssignment
from models.enrollment import Enrollment
from models.professor_availability import ProfessorAvailability
from models.session_booking import BookingStatus, SessionBooking
from models.user import User, UserRole
from schemas.professor_availability import AvailabilityCreate, AvailabilityRead, AvailabilityUpdate

router = APIRouter(prefix="/availability", tags=["availability"])


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_read(slot: ProfessorAvailability, booked_count: int) -> AvailabilityRead:
    return AvailabilityRead(
        id=slot.id,
        professor_id=slot.professor_id,
        course_id=slot.course_id,
        start_time=slot.start_time,
        end_time=slot.end_time,
        max_students=slot.max_students,
        booked_count=booked_count,
        created_at=slot.created_at,
    )


async def _get_slot_or_404(db: AsyncSession, availability_id: uuid.UUID) -> ProfessorAvailability:
    slot = await db.get(ProfessorAvailability, availability_id)
    if not slot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Availability window not found")
    return slot


async def _booked_counts(db: AsyncSession, availability_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    """Return a mapping of availability_id → active booking count."""
    if not availability_ids:
        return {}
    rows = await db.execute(
        select(SessionBooking.availability_id, func.count(SessionBooking.id))
        .where(
            SessionBooking.availability_id.in_(availability_ids),
            SessionBooking.status != BookingStatus.cancelled,
        )
        .group_by(SessionBooking.availability_id)
    )
    return {row[0]: row[1] for row in rows.all()}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/", response_model=AvailabilityRead, status_code=status.HTTP_201_CREATED)
async def create_availability(
    payload: AvailabilityCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(professor_only),
):
    """
    Professor creates an availability window for a course they are assigned to.
    Admins may create on behalf of any professor (assignment check skipped).
    """
    professor_id = current_user.id

    if current_user.role == UserRole.professor:
        assignment = await db.scalars(
            select(CourseAssignment).where(
                CourseAssignment.user_id   == professor_id,
                CourseAssignment.course_id == payload.course_id,
            )
        )
        if not assignment.first():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not assigned to this course",
            )

    slot = ProfessorAvailability(
        professor_id=professor_id,
        course_id=payload.course_id,
        start_time=payload.start_time,
        end_time=payload.end_time,
        max_students=payload.max_students,
    )
    db.add(slot)
    await db.commit()
    await db.refresh(slot)
    return _build_read(slot, 0)


@router.get("/", response_model=list[AvailabilityRead])
async def list_availability(
    course_id:    Optional[uuid.UUID] = Query(None),
    professor_id: Optional[uuid.UUID] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List availability windows.
    - Admin: all windows (filterable).
    - Professor: only their own windows (filterable by course).
    - Student: windows for courses they are enrolled in (filterable).
    """
    q = select(ProfessorAvailability)

    if current_user.role == UserRole.admin:
        if course_id:
            q = q.where(ProfessorAvailability.course_id == course_id)
        if professor_id:
            q = q.where(ProfessorAvailability.professor_id == professor_id)

    elif current_user.role == UserRole.professor:
        q = q.where(ProfessorAvailability.professor_id == current_user.id)
        if course_id:
            q = q.where(ProfessorAvailability.course_id == course_id)

    else:  # student
        enrolled = select(Enrollment.course_id).where(Enrollment.user_id == current_user.id)
        q = q.where(ProfessorAvailability.course_id.in_(enrolled))
        if course_id:
            q = q.where(ProfessorAvailability.course_id == course_id)
        if professor_id:
            q = q.where(ProfessorAvailability.professor_id == professor_id)

    slots = (await db.scalars(q)).all()
    counts = await _booked_counts(db, [s.id for s in slots])
    return [_build_read(s, counts.get(s.id, 0)) for s in slots]


@router.get("/{availability_id}", response_model=AvailabilityRead)
async def get_availability(
    availability_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    slot = await _get_slot_or_404(db, availability_id)
    counts = await _booked_counts(db, [slot.id])
    return _build_read(slot, counts.get(slot.id, 0))


@router.patch("/{availability_id}", response_model=AvailabilityRead)
async def update_availability(
    availability_id: uuid.UUID,
    payload: AvailabilityUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(professor_only),
):
    """Professor updates their own window. Admins can update any."""
    slot = await _get_slot_or_404(db, availability_id)

    if current_user.role == UserRole.professor and slot.professor_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your availability window")

    updates = payload.model_dump(exclude_unset=True)

    # validate end > start after merge
    new_start = updates.get("start_time", slot.start_time)
    new_end   = updates.get("end_time",   slot.end_time)
    if new_end <= new_start:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="end_time must be after start_time")

    for field, value in updates.items():
        setattr(slot, field, value)

    await db.commit()
    await db.refresh(slot)
    counts = await _booked_counts(db, [slot.id])
    return _build_read(slot, counts.get(slot.id, 0))


@router.delete("/{availability_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_availability(
    availability_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(professor_only),
):
    """Professor deletes their own window (cascades to bookings). Admins can delete any."""
    slot = await _get_slot_or_404(db, availability_id)

    if current_user.role == UserRole.professor and slot.professor_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your availability window")

    await db.delete(slot)
    await db.commit()
