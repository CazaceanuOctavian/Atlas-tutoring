# Import all models here so SQLAlchemy registers them on Base.metadata.
# This is required for Alembic autogenerate and Base.metadata.create_all().

from models.chapter import Chapter
from models.course import Course
from models.course_assignment import CourseAssignment
from models.enrollment import Enrollment
from models.professor_availability import ProfessorAvailability
from models.session_booking import SessionBooking
from models.exercise import Exercise
from models.exercise_block import ExerciseBlock
from models.lecture import Lecture
from models.lecture_block import LectureBlock
from models.test_case import TestCase
from models.user import User
from models.submission import Submission
from models.submission_test_result import SubmissionTestResult
from models.auth_handoff import AuthHandoff


__all__ = [
    "User",
    "Course",
    "CourseAssignment",
    "Enrollment",
    "ProfessorAvailability",
    "SessionBooking",
    "Chapter",
    "Lecture",
    "LectureBlock",
    "Exercise",
    "ExerciseBlock",
    "TestCase",
    "Submission",
    "SubmissionTestResult",
    "AuthHandoff",
]
