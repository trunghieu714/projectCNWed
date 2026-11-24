from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime
from .user import UserResponse
from ..models.entities import EnrollmentStatus

class CourseBase(BaseModel):
    title: str
    description: Optional[str] = None
    max_students: int = 500

class CourseCreate(CourseBase):
    pass

class CourseResponse(CourseBase):
    id: int
    teacher_id: int
    created_at: datetime
    teacher: Optional[UserResponse] = None
    students_count: Optional[int] = 0

    model_config = ConfigDict(from_attributes=True)

class CourseMemberResponse(BaseModel):
    id: int
    course_id: int
    student_id: int
    status: EnrollmentStatus
    joined_at: datetime
    student: Optional[UserResponse] = None

    model_config = ConfigDict(from_attributes=True)
