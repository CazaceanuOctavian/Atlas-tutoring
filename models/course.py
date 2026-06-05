import uuid

from sqlalchemy import Column, DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base import Base


class Course(Base):
    __tablename__ = "courses"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title       = Column(String(255), nullable=False)
    description = Column(Text)
    created_at  = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    enrollments = relationship(
        "Enrollment", back_populates="course", cascade="all, delete-orphan"
    )
    chapters = relationship(
        "Chapter", back_populates="course", cascade="all, delete-orphan",
        order_by="Chapter.position",
    )