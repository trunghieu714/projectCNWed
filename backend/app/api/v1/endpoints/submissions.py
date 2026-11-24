import os
import shutil
from typing import List
from fastapi import APIRouter, Depends, UploadFile, Form, HTTPException, status
from sqlalchemy.orm import Session
from ....core.database import get_db
from ....core.config import settings
from ....services.video_service import save_video_upload
from ....services.submission_service import SubmissionService
from ....schemas.submission import SubmissionResponse
from ....models.entities import User
from ...deps import get_current_user, validate_video_file

router = APIRouter()

@router.post("/submit", response_model=SubmissionResponse, status_code=status.HTTP_202_ACCEPTED)
async def submit_video(
    exercise_id: int = Form(...),
    file: UploadFile = Depends(validate_video_file),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Endpoint nhận video bài tập:
    1. Xác thực người dùng qua JWT Bearer token
    2. Xác thực định dạng và dung lượng video
    3. Đẩy sang Celery Worker xử lý bất đồng bộ
    """
    normalized_video_path = save_video_upload(file, f"user_{current_user.id}_ex_{exercise_id}")

    service = SubmissionService(db)
    submission = service.submit_exercise(
        exercise_id=exercise_id,
        student_id=current_user.id,
        video_path=normalized_video_path
    )
    return submission

@router.get("/my-history", response_model=List[SubmissionResponse])
def get_my_submissions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    service = SubmissionService(db)
    return service.get_student_submissions(current_user.id)

@router.get("/{submission_id}", response_model=SubmissionResponse)
def get_submission(
    submission_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    service = SubmissionService(db)
    sub = service.get_submission_detail(submission_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Không tìm thấy bài nộp.")
    return sub

@router.get("/exercise/{exercise_id}", response_model=List[SubmissionResponse])
def get_exercise_submissions(
    exercise_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Lấy danh sách các bài nộp của học viên cho bài tập cụ thể (phục vụ HLV theo dõi)."""
    service = SubmissionService(db)
    return service.get_exercise_submissions(exercise_id)
