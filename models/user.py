import uuid
import enum

from sqlalchemy import Column, DateTime, String, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from models.base import Base


class UserRole(str, enum.Enum):
    admin     = "admin"
    professor = "professor"
    student   = "student"


class User(Base):
    __tablename__ = "users"

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name          = Column(String(255), nullable=False)
    email         = Column(String(255), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=True)
    role          = Column(Enum(UserRole), nullable=False, default=UserRole.student)
    created_at    = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    google_sub = Column(String(255), unique=True, nullable=True, index=True)

    enrollments = relationship(
        "Enrollment", back_populates="user", cascade="all, delete-orphan"
    )
    course_assignments = relationship(
        "CourseAssignment", back_populates="user", cascade="all, delete-orphan"
    )
    submissions = relationship(
        "Submission", back_populates="student", cascade="all, delete-orphan"
    )