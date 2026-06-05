import uuid

from sqlalchemy import Column, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .base import Base


class LectureBlock(Base):
    __tablename__ = "lecture_blocks"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lecture_id = Column(UUID(as_uuid=True), ForeignKey("lectures.id", ondelete="CASCADE"), nullable=False)
    markdown   = Column(Text, nullable=False)
    position   = Column(Integer, nullable=False, default=0)

    lecture = relationship("Lecture", back_populates="blocks")