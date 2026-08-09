import uuid

from sqlalchemy import Boolean, Column, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from models.base import Base


class SubmissionTestResult(Base):
    __tablename__ = "submission_test_results"

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    submission_id = Column(UUID(as_uuid=True), ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False)
    test_case_id  = Column(UUID(as_uuid=True), ForeignKey("test_cases.id",  ondelete="CASCADE"), nullable=False)
    order_index   = Column(Integer, nullable=False)
    passed        = Column(Boolean, nullable=False)
    actual_output = Column(Text, nullable=True)
    stderr        = Column(Text, nullable=True)
    exit_code     = Column(Text, nullable=True)
    timed_out     = Column(Boolean, nullable=False, default=False)

    submission = relationship("Submission",  back_populates="test_results")
    test_case  = relationship("TestCase")
