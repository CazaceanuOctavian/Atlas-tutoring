import uuid

from sqlalchemy import Column, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base import Base


class CourseAssignment(Base):
    __tablename__ = "course_assignments"
    __table_args__ = (UniqueConstraint("user_id", "course_id"),)

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id     = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    course_id   = Column(UUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    assigned_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    user   = relationship("User",   back_populates="course_assignments")
    course = relationship("Course", back_populates="professor_assignments")
