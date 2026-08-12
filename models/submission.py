import uuid
import enum

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Text, Enum, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from models.base import Base


class Language(str, enum.Enum):
    python = "python"
    cpp    = "cpp"


class SubmissionStatus(str, enum.Enum):
    queued  = "queued"
    running = "running"
    passed  = "passed"
    failed  = "failed"
    error   = "error"
    timeout = "timeout"


class Submission(Base):
    __tablename__ = "submissions"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    exercise_id = Column(UUID(as_uuid=True), ForeignKey("exercises.id", ondelete="CASCADE"), nullable=False)
    student_id  = Column(UUID(as_uuid=True), ForeignKey("users.id",     ondelete="CASCADE"), nullable=False)
    code        = Column(Text, nullable=False)
    language    = Column(Enum(Language), nullable=False)
    status      = Column(Enum(SubmissionStatus), nullable=False, default=SubmissionStatus.queued)
    created_at  = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # Execution result — populated after the runner finishes (last test case run, or the raw run if no test cases)
    stdout           = Column(Text,  nullable=True)
    stderr           = Column(Text,  nullable=True)
    timed_out        = Column(Boolean, nullable=True)
    exit_code        = Column(Text,  nullable=True)

    # Test case grading — null when there are no test cases
    passed_count = Column(Integer, nullable=True)
    total_count  = Column(Integer, nullable=True)

    exercise     = relationship("Exercise",            back_populates="submissions")
    student      = relationship("User",                back_populates="submissions")
    test_results = relationship(
        "SubmissionTestResult",
        back_populates="submission",
        cascade="all, delete-orphan",
        order_by="SubmissionTestResult.order_index",
    )