import uuid

from sqlalchemy import Column, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from models.base import Base


class Exercise(Base):
    __tablename__ = "exercises"

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lecture_id    = Column(UUID(as_uuid=True), ForeignKey("lectures.id", ondelete="CASCADE"), nullable=False)
    title         = Column(String(255), nullable=False)
    position      = Column(Integer, nullable=False, default=0)
    code_template = Column(Text, nullable=True)

    lecture    = relationship("Lecture", back_populates="exercises")
    blocks     = relationship(
        "ExerciseBlock", back_populates="exercise", cascade="all, delete-orphan",
        order_by="ExerciseBlock.position",
    )
    test_cases = relationship(
        "TestCase", back_populates="exercise", cascade="all, delete-orphan"
    )
    submissions = relationship(
        "Submission", back_populates="exercise", cascade="all, delete-orphan"
    )