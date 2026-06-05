import uuid

from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .base import Base


class Chapter(Base):
    __tablename__ = "chapters"

    id        = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    course_id = Column(UUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    title     = Column(String(255), nullable=False)
    position  = Column(Integer, nullable=False, default=0)

    course   = relationship("Course",  back_populates="chapters")
    lectures = relationship(
        "Lecture", back_populates="chapter", cascade="all, delete-orphan",
        order_by="Lecture.position",
    )