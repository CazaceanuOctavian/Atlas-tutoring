import uuid
import enum

from sqlalchemy import Column, DateTime, ForeignKey, Text, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from models.base import Base


class Language(str, enum.Enum):
    python = "python"
    cpp    = "cpp"


class Submission(Base):
    __tablename__ = "submissions"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    exercise_id = Column(UUID(as_uuid=True), ForeignKey("exercises.id", ondelete="CASCADE"), nullable=False)
    student_id  = Column(UUID(as_uuid=True), ForeignKey("users.id",     ondelete="CASCADE"), nullable=False)
    code        = Column(Text, nullable=False)
    language    = Column(Enum(Language), nullable=False)
    created_at  = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    exercise = relationship("Exercise", back_populates="submissions")
    student  = relationship("User",     back_populates="submissions")