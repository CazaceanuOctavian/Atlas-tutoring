import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.session import get_db
from dependencies import get_current_user
from models.enrollment import Enrollment
from models.professor_availability import ProfessorAvailability
from models.session_booking import BookingStatus, SessionBooking
from models.user import User, UserRole
from pagination import as_page, count_query
from schemas.common import CourseSummary, Page, UserSummary
from schemas.session_booking import BookingCreate, BookingRead, BookingStatusUpdate, BookingWithRefs

router = APIRouter(prefix="/bookings", tags=["bookings"])


def _serialize_bookings(bookings, expand: set[str]) -> list[BookingWithRefs]:
    items = []
    for b in bookings:
        # Scalar columns only, then attach refs — never let from_attributes
        # read b.student / b.professor / b.course (async lazy-load trap).
        item = BookingWithRefs(**BookingRead.model_validate(b).model_dump())
        if "student" in expand and b.student is not None:
            item.student = UserSummary.model_validate(b.student)
        if "professor" in expand and b.professor is not None:
            item.professor = UserSummary.model_validate(b.professor)
        if "course" in expand and b.course is not None:
            item.course = CourseSummary.model_validate(b.course)
        items.append(item)
    return items


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _get_booking_or_404(db: AsyncSession, booking_id: uuid.UUID) -> SessionBooking:
    booking = await db.get(SessionBooking, booking_id)
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    return booking


async def _active_booking_count(db: AsyncSession, availability_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count(SessionBooking.id)).where(
            SessionBooking.availability_id == availability_id,
            SessionBooking.status != BookingStatus.cancelled,
        )
    )
    return result.scalar_one()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/", response_model=BookingRead, status_code=status.HTTP_201_CREATED)
async def create_booking(
    payload: BookingCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Student books a session within a professor's availability window.
    Validates: enrollment in the course, time bounds, and remaining capacity.
    """
    if current_user.role != UserRole.student:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can create bookings",
        )

    slot = await db.get(ProfessorAvailability, payload.availability_id)
    if not slot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Availability window not found")

    # student must be enrolled in the course
    enrollment = await db.scalars(
        select(Enrollment).where(
            Enrollment.user_id   == current_user.id,
            Enrollment.course_id == slot.course_id,
        )
    )
    if not enrollment.first():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not enrolled in the course this availability belongs to",
        )

    # overlap check — student cannot have two active bookings at the same time
    overlap = await db.scalars(
        select(SessionBooking).where(
            SessionBooking.student_id == current_user.id,
            SessionBooking.status != BookingStatus.cancelled,
            SessionBooking.start_time < slot.end_time,
            SessionBooking.end_time > slot.start_time,
        )
    )
    if overlap.first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have a booking that overlaps with this time slot",
        )

    # capacity check
    active = await _active_booking_count(db, slot.id)
    if active >= slot.max_students:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This availability window is fully booked",
        )

    booking = SessionBooking(
        student_id      = current_user.id,
        professor_id    = slot.professor_id,
        course_id       = slot.course_id,
        availability_id = slot.id,
        start_time      = slot.start_time,
        end_time        = slot.end_time,
    )
    db.add(booking)
    await db.commit()
    await db.refresh(booking)
    return booking


@router.get("/", response_model=list[BookingWithRefs] | Page[BookingWithRefs])
async def list_bookings(
    course_id:       Optional[uuid.UUID]  = Query(None),
    availability_id: Optional[uuid.UUID]  = Query(None),
    student_id:      Optional[uuid.UUID]  = Query(None),
    professor_id:    Optional[uuid.UUID]  = Query(None),
    status_:         Optional[BookingStatus] = Query(None, alias="status"),
    since:           Optional[datetime]   = Query(None, description="start_time >= since"),
    until:           Optional[datetime]   = Query(None, description="start_time <= until"),
    expand:          Optional[str]        = Query(None, description="Comma list: student, professor, course."),
    skip:            int                  = Query(0, ge=0),
    limit:           int                  = Query(50, ge=1, le=200),
    envelope:        bool                 = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List bookings scoped by role.
    - Admin: all bookings.
    - Professor: bookings on their availability windows.
    - Student: their own bookings.
    """
    stmt = select(SessionBooking)

    if current_user.role == UserRole.admin:
        pass  # no extra filter
    elif current_user.role == UserRole.professor:
        stmt = stmt.where(SessionBooking.professor_id == current_user.id)
    else:
        stmt = stmt.where(SessionBooking.student_id == current_user.id)

    if course_id:
        stmt = stmt.where(SessionBooking.course_id == course_id)
    if availability_id:
        stmt = stmt.where(SessionBooking.availability_id == availability_id)
    if student_id:
        stmt = stmt.where(SessionBooking.student_id == student_id)
    if professor_id:
        stmt = stmt.where(SessionBooking.professor_id == professor_id)
    if status_ is not None:
        stmt = stmt.where(SessionBooking.status == status_)
    if since is not None:
        stmt = stmt.where(SessionBooking.start_time >= since)
    if until is not None:
        stmt = stmt.where(SessionBooking.start_time <= until)

    expand_set = {s.strip() for s in (expand or "").split(",") if s.strip()}
    if "student" in expand_set:
        stmt = stmt.options(selectinload(SessionBooking.student))
    if "professor" in expand_set:
        stmt = stmt.options(selectinload(SessionBooking.professor))
    if "course" in expand_set:
        stmt = stmt.options(selectinload(SessionBooking.course))

    stmt = stmt.order_by(SessionBooking.start_time.desc())
    total = await count_query(db, stmt) if envelope else 0
    rows = (await db.scalars(stmt.offset(skip).limit(limit))).all()
    items = _serialize_bookings(rows, expand_set)
    return as_page(items, total, skip, limit, envelope)


@router.get("/{booking_id}", response_model=BookingRead)
async def get_booking(
    booking_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    booking = await _get_booking_or_404(db, booking_id)

    if current_user.role == UserRole.admin:
        return booking
    if current_user.role == UserRole.professor and booking.professor_id == current_user.id:
        return booking
    if current_user.role == UserRole.student and booking.student_id == current_user.id:
        return booking

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")


@router.patch("/{booking_id}", response_model=BookingRead)
async def update_booking_status(
    booking_id: uuid.UUID,
    payload: BookingStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update booking status.
    - Professor (owner): can set confirmed or cancelled.
    - Student (owner): can only cancel.
    - Admin: any transition.
    """
    booking = await _get_booking_or_404(db, booking_id)

    if current_user.role == UserRole.admin:
        pass
    elif current_user.role == UserRole.professor:
        if booking.professor_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your booking")
    elif current_user.role == UserRole.student:
        if booking.student_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your booking")
        if payload.status != BookingStatus.cancelled:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Students can only cancel their bookings",
            )
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    booking.status = payload.status
    await db.commit()
    await db.refresh(booking)
    return booking
