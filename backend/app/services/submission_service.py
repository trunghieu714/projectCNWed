import socket
from typing import Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from ..repositories.submission_repository import SubmissionRepository
from ..repositories.exercise_repository import ExerciseRepository
from ..models.entities import SocialPost
from ..workers.video_tasks import evaluate_submission_video, process_submission_core

def is_redis_available() -> bool:
    """Kiểm tra nhanh xem Redis server có đang lắng nghe cổng không mà không làm block luồng."""
    try:
        from urllib.parse import urlparse
        from ..core.config import settings
        parsed = urlparse(settings.CELERY_BROKER_URL)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 6379
        sock = socket.create_connection((host, port), timeout=0.3)
        sock.close()
        return True
    except (socket.error, Exception):
        return False

class SubmissionService:
    def __init__(self, db: Session):
        self.db = db
        self.sub_repo = SubmissionRepository(db)
        self.ex_repo = ExerciseRepository(db)

    def submit_exercise(self, exercise_id: int, student_id: int, video_path: str, post_id: Optional[int] = None,
                        right_video_path: Optional[str] = None):
        # 1. Kiểm tra bài tập có tồn tại trong Database không
        exercise = self.ex_repo.get_by_id(exercise_id)
        if not exercise:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Bài tập ID {exercise_id} không tồn tại trong hệ thống."
            )

        # 2. Tạo bản ghi Submission ở trạng thái PENDING
        submission = self.sub_repo.create(
            exercise_id=exercise_id,
            student_id=student_id,
            video_url=video_path
        )
        if right_video_path:
            submission.student_video_right_url = right_video_path
            self.db.commit()

        # 3. Liên kết ngay với SocialPost nếu có (để Auto-comment bot nhận diện đúng bài đăng)
        if post_id:
            post = self.db.query(SocialPost).filter(SocialPost.id == post_id).first()
            if post:
                post.submission_id = submission.id
                self.db.commit()

        # 4. Đẩy sang Celery nếu Redis khả dụng, hoặc fallback đồng bộ an toàn
        if is_redis_available():
            try:
                task = evaluate_submission_video.delay(submission.id)
                submission.task_id = task.id
                self.db.commit()
                self.db.refresh(submission)
            except Exception:
                process_submission_core(submission.id)
                self.db.refresh(submission)
        else:
            # Fallback nếu Redis chưa bật: chạy trực tiếp không gián đoạn
            process_submission_core(submission.id)
            self.db.refresh(submission)

        return submission

    def get_submission_detail(self, submission_id: int):
        return self.sub_repo.get_by_id(submission_id)

    def get_student_submissions(self, student_id: int):
        return self.sub_repo.get_by_student(student_id)

    def get_exercise_submissions(self, exercise_id: int):
        return self.sub_repo.get_by_exercise(exercise_id)
