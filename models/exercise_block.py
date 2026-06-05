import uuid

from sqlalchemy import Column, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .base import Base


class ExerciseBlock(Base):
    __tablename__ = "exercise_blocks"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    exercise_id = Column(UUID(as_uuid=True), ForeignKey("exercises.id", ondelete="CASCADE"), nullable=False)
    markdown    = Column(Text, nullable=False)
    position    = Column(Integer, nullable=False, default=0)

    exercise = relationship("Exercise", back_populates="blocks")