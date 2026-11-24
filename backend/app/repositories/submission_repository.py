from typing import List, Optional
from sqlalchemy.orm import Session
from ..models.entities import Submission, SubmissionStatus

class SubmissionRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, submission_id: int) -> Optional[Submission]:
        return self.db.query(Submission).filter(Submission.id == submission_id).first()

    def get_by_student(self, student_id: int, skip: int = 0, limit: int = 20) -> List[Submission]:
        return self.db.query(Submission).filter(Submission.student_id == student_id).order_by(Submission.created_at.desc()).offset(skip).limit(limit).all()

    def get_by_exercise(self, exercise_id: int, skip: int = 0, limit: int = 50) -> List[Submission]:
        return self.db.query(Submission).filter(Submission.exercise_id == exercise_id).order_by(Submission.created_at.desc()).offset(skip).limit(limit).all()

    def create(self, exercise_id: int, student_id: int, video_url: str) -> Submission:
        submission = Submission(
            exercise_id=exercise_id,
            student_id=student_id,
            student_video_url=video_url,
            status=SubmissionStatus.PENDING
        )
        self.db.add(submission)
        self.db.commit()
        self.db.refresh(submission)
        return submission

    def set_processing(self, submission_id: int, task_id: Optional[str] = None) -> Optional[Submission]:
        sub = self.get_by_id(submission_id)
        if sub:
            sub.status = SubmissionStatus.PROCESSING
            if task_id:
                sub.task_id = task_id
            self.db.commit()
            self.db.refresh(sub)
        return sub

    def set_completed(self, submission_id: int, score: float, feedback: str, fused_video_url: str) -> Optional[Submission]:
        sub = self.get_by_id(submission_id)
        if sub:
            sub.score = score
            sub.feedback_text = feedback
            sub.fused_video_url = fused_video_url
            sub.status = SubmissionStatus.COMPLETED
            self.db.commit()
            self.db.refresh(sub)
        return sub

    def set_failed(self, submission_id: int, error_msg: str) -> Optional[Submission]:
        sub = self.get_by_id(submission_id)
        if sub:
            sub.status = SubmissionStatus.FAILED
            sub.error_message = error_msg
            self.db.commit()
            self.db.refresh(sub)
        return sub
