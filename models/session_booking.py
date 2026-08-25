import uuid
import enum

from sqlalchemy import Column, DateTime, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base import Base


class BookingStatus(str, enum.Enum):
    pending   = "pending"
    confirmed = "confirmed"
    cancelled = "cancelled"


class SessionBooking(Base):
    __tablename__ = "session_bookings"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id      = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    professor_id    = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    course_id       = Column(UUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    availability_id = Column(UUID(as_uuid=True), ForeignKey("professor_availability.id", ondelete="CASCADE"), nullable=False)
    start_time      = Column(DateTime(timezone=True), nullable=False)
    end_time        = Column(DateTime(timezone=True), nullable=False)
    status          = Column(Enum(BookingStatus), nullable=False, default=BookingStatus.pending)
    created_at      = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    student      = relationship("User",                  foreign_keys=[student_id],   back_populates="bookings_as_student")
    professor    = relationship("User",                  foreign_keys=[professor_id], back_populates="bookings_as_professor")
    course       = relationship("Course",                back_populates="bookings")
    availability = relationship("ProfessorAvailability", back_populates="bookings")
