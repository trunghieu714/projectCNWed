from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime
from .user import UserResponse
from .submission import SubmissionResponse
from .comment import CommentResponse

class PostBase(BaseModel):
    content: str
    submission_id: Optional[int] = None
    course_id: Optional[int] = None
    exercise_id: Optional[int] = None
    video_left_url: Optional[str] = None
    video_right_url: Optional[str] = None
    video_fused_url: Optional[str] = None

class PostCreate(PostBase):
    pass

class PostEdit(BaseModel):
    content: Optional[str] = None
    video_left_url: Optional[str] = None
    video_right_url: Optional[str] = None

class PostAuthor(BaseModel):
    id: int
    username: str
    full_name: Optional[str] = None
    role: str
    avatar_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class PostResponse(BaseModel):
    id: int
    user_id: int
    course_id: Optional[int] = None
    exercise_id: Optional[int] = None
    submission_id: Optional[int] = None
    content: str
    video_left_url: Optional[str] = None
    video_right_url: Optional[str] = None
    video_fused_url: Optional[str] = None
    device_master: Optional[str] = None
    device_slave: Optional[str] = None
    likes_count: int = 0
    created_at: datetime
    updated_at: Optional[datetime] = None
    author: Optional[PostAuthor] = None
    submission: Optional[SubmissionResponse] = None
    comments: Optional[List[CommentResponse]] = []

    model_config = ConfigDict(from_attributes=True)
