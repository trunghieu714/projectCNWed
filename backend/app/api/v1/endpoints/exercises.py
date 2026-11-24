import os
import shutil
from typing import List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, UploadFile, File, Form, HTTPException, status
from sqlalchemy.orm import Session
from ....core.database import get_db
from ....core.config import settings
from ....services.video_service import save_video_upload
from ....models.entities import User
from ....schemas.exercise import ExerciseResponse
from ....repositories.exercise_repository import ExerciseRepository
from ...deps import get_current_coach, validate_video_file

router = APIRouter()

@router.get("/", response_model=List[ExerciseResponse])
def get_exercises(
    category: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    repo = ExerciseRepository(db)
    return repo.get_all(category=category, skip=skip, limit=limit)

@router.get("/{exercise_id}", response_model=ExerciseResponse)
def get_exercise_detail(exercise_id: int, db: Session = Depends(get_db)):
    repo = ExerciseRepository(db)
    exercise = repo.get_by_id(exercise_id)
    if not exercise:
        raise HTTPException(status_code=404, detail="Không tìm thấy bài tập.")
    return exercise

@router.post("/", response_model=ExerciseResponse, status_code=status.HTTP_201_CREATED)
async def create_exercise(
    background: BackgroundTasks,
    title: str = Form(...),
    category: str = Form(...),
    description: Optional[str] = Form(None),
    file: UploadFile = Depends(validate_video_file),
    current_coach: User = Depends(get_current_coach),
    db: Session = Depends(get_db)
):
    # Bài tập của GV chính là một bài đăng có video chuẩn (Slide 5 & add_post Slide 40):
    # tạo bài viết qua cùng nghiệp vụ với add_post để bài tập hiện trên bảng tin và HV bấm "Nộp bài" được
    from ....services.post_service import PostService
    described = f"{title}\n{description}" if description else title
    post = PostService(db, background).add_post(current_coach, described, left_video=file)
    exercise = post.exercise
    if exercise is None:
        raise HTTPException(status_code=400, detail="Chỉ tài khoản giáo viên mới tạo được bài tập.")
    exercise.title = title
    exercise.category = category
    exercise.description = description
    db.commit()
    db.refresh(exercise)
    return exercise
