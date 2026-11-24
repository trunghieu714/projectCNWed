from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime
from .user import UserResponse

class FrameError(BaseModel):
    coach_frame: int
    student_frame: int
    max_angle_error: float
    status: str

class SubmissionResponse(BaseModel):
    id: int
    exercise_id: int
    student_id: int
    student_video_url: str
    fused_video_url: Optional[str] = None
    status: str
    score: Optional[float] = None
    feedback_text: Optional[str] = None
    error_message: Optional[str] = None
    task_id: Optional[str] = None
    student_video_right_url: Optional[str] = None
    report_html_url: Optional[str] = None
    result_json: Optional[str] = None
    created_at: datetime
    student: Optional[UserResponse] = None

    model_config = ConfigDict(from_attributes=True)
