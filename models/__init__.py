# Import all models here so SQLAlchemy registers them on Base.metadata.
# This is required for Alembic autogenerate and Base.metadata.create_all().

from models.chapter import Chapter
from models.course import Course
from models.enrollment import Enrollment
from models.exercise import Exercise
from models.exercise_block import ExerciseBlock
from models.lecture import Lecture
from models.lecture_block import LectureBlock
from models.test_case import TestCase
from models.user import User

__all__ = [
    "User",
    "Course",
    "Enrollment",
    "Chapter",
    "Lecture",
    "LectureBlock",
    "Exercise",
    "ExerciseBlock",
    "TestCase",
]