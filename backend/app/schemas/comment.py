from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime
from .user import UserResponse

class CommentBase(BaseModel):
    content: str

class CommentCreate(CommentBase):
    post_id: int

class CommentResponse(CommentBase):
    id: int
    post_id: int
    user_id: Optional[int] = None
    is_bot_evaluation: bool = False
    created_at: datetime
    user: Optional[UserResponse] = None

    model_config = ConfigDict(from_attributes=True)
