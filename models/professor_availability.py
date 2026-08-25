import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base import Base


class ProfessorAvailability(Base):
    __tablename__ = "professor_availability"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    professor_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    course_id    = Column(UUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    start_time   = Column(DateTime(timezone=True), nullable=False)
    end_time     = Column(DateTime(timezone=True), nullable=False)
    max_students = Column(Integer, nullable=False, default=1)
    created_at   = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    professor = relationship("User",   foreign_keys=[professor_id], back_populates="availability_slots")
    course    = relationship("Course", back_populates="availability_slots")
    bookings  = relationship("SessionBooking", back_populates="availability", cascade="all, delete-orphan")
