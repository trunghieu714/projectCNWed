from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class ExerciseBase(BaseModel):
    title: str
    category: str
    description: Optional[str] = None
    course_id: Optional[int] = None

class ExerciseCreate(ExerciseBase):
    pass

class ExerciseResponse(ExerciseBase):
    id: int
    coach_video_url: str
    coach_pose_cache_url: Optional[str] = None
    post_id: Optional[int] = None
    created_by: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
