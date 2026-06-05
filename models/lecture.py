import uuid

from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .base import Base


class Lecture(Base):
    __tablename__ = "lectures"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chapter_id = Column(UUID(as_uuid=True), ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False)
    title      = Column(String(255), nullable=False)
    position   = Column(Integer, nullable=False, default=0)

    chapter   = relationship("Chapter",  back_populates="lectures")
    blocks    = relationship(
        "LectureBlock", back_populates="lecture", cascade="all, delete-orphan",
        order_by="LectureBlock.position",
    )
    exercises = relationship(
        "Exercise", back_populates="lecture", cascade="all, delete-orphan",
        order_by="Exercise.position",
    )