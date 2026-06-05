import uuid

from sqlalchemy import Column, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .base import Base


class TestCase(Base):
    __tablename__ = "test_cases"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    exercise_id     = Column(UUID(as_uuid=True), ForeignKey("exercises.id", ondelete="CASCADE"), nullable=False)
    input           = Column(Text)
    expected_output = Column(Text, nullable=False)
    description     = Column(String(255))

    exercise = relationship("Exercise", back_populates="test_cases")