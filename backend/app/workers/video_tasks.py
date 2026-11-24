import json
import os
import traceback
from typing import Optional
from .celery_app import celery_app
from ..core.config import settings
from ..core.database import SessionLocal
from ..repositories.submission_repository import SubmissionRepository
from ..repositories.exercise_repository import ExerciseRepository
from ..repositories.comment_repository import CommentRepository
from ..models.entities import SocialPost
from ..services.notification_service import NotificationService
from ..services.video_service import to_url
from ai_engine.factory import AIEngineFactory

def resolve_storage_path(path: Optional[str]) -> str:
    if not path:
        return ""
    if os.path.exists(path):
        return path
    clean = path.lstrip("/")
    if os.path.exists(clean):
        return clean
    app_path = os.path.join("/app", clean)
    if os.path.exists(app_path):
        return app_path
    return clean

def _json_default(o):
    try:
        import numpy as np
        if isinstance(o, np.generic):
            return o.item()
        if isinstance(o, np.ndarray):
            return o.tolist()
    except ImportError:
        pass
    return str(o)

def process_submission_core(submission_id: int, task_id: Optional[str] = None):
    """
    Quy trình đánh giá bài nộp (Slide 8, 42 & FAQ Q3):
    1. Đổi trạng thái sang PROCESSING
    2. Lấy video HLV (1-2 góc quay) từ bài tập, video HV (1-2 góc quay) từ bài nộp
    3. Chạy pipeline AI theo cấu hình .env (Pose 3D -> DTW PA-MPJPE -> video fused + báo cáo HTML)
    4. Cập nhật kết quả COMPLETED hoặc FAILED
    5. Bot AI tự động comment điểm số + chi tiết lỗi (HTML) vào bài đăng của học viên
    """
    db = SessionLocal()
    sub_repo = SubmissionRepository(db)
    ex_repo = ExerciseRepository(db)
    comment_repo = CommentRepository(db)
    notifier = NotificationService(db)
    post = None

    try:
        sub = sub_repo.get_by_id(submission_id)
        if not sub:
            return {"error": f"Không tìm thấy submission_id {submission_id}"}

        sub_repo.set_processing(submission_id, task_id=task_id)
        post = db.query(SocialPost).filter(SocialPost.submission_id == submission_id).first()

        exercise = ex_repo.get_by_id(sub.exercise_id)
        coach_left = resolve_storage_path(exercise.coach_video_url if exercise else "storage/coach_samples/coach_sample.mp4")
        coach_right = resolve_storage_path(exercise.coach_video_right_url) if exercise and exercise.coach_video_right_url else None
        student_left = resolve_storage_path(sub.student_video_url)
        student_right = resolve_storage_path(sub.student_video_right_url) if sub.student_video_right_url else None

        pipeline = AIEngineFactory.create_pipeline_from_settings(settings)
        output_dir = os.path.join(settings.OUTPUT_DIR, f"sub_{submission_id}")
        os.makedirs(output_dir, exist_ok=True)

        title = f"Kết quả chấm điểm: {exercise.title}" if exercise else "Kết quả chấm điểm động tác"
        result = pipeline.run_multi_view_assessment(
            coach_videos={"left": coach_left, "right": coach_right},
            student_videos={"left": student_left, "right": student_right},
            output_dir=output_dir,
            title=title,
        )

        score = result["score"]
        feedback = result["summary"]
        fused_video_url = to_url(result["fused_video_url"])
        report_url = to_url(result["report_path"])

        sub_repo.set_completed(submission_id=submission_id, score=score, feedback=feedback, fused_video_url=fused_video_url)
        sub = sub_repo.get_by_id(submission_id)
        sub.report_html_url = report_url
        detail = {
            "score": score,
            "metric": result.get("metric"),
            "pose_source": result.get("pose_source"),
            # warping path theo chỉ số frame video (dùng cho trình phát đồng bộ HLV - HV)
            "warping_path": (result.get("video_warping_path") or result.get("warping_path", []))[:3000],
            "errors": [{k: e.get(k) for k in ("coach_frame", "student_frame", "error_percent", "max_angle_error", "worst_joints", "status")}
                       for e in result.get("errors", [])][:500],
            "sides": {
                side: {k: v for k, v in r.items() if k in (
                    "final_score", "mean_error", "mean_pa_mpjpe", "unit", "segments", "top_joints",
                    "joint_mean_errors", "per_frame_error", "pose_source", "feedback_summary")}
                for side, r in result.get("sides", {}).items()
            },
        }
        sub.result_json = json.dumps(detail, ensure_ascii=False, default=_json_default)
        db.commit()

        # 🤖 AI AUTO-COMMENT BOT (FAQ Q3 & Slide 42): comment điểm số vào bài viết của Học viên
        if post:
            rating_str = "XUẤT SẮC" if score >= 90 else ("ĐẠT YÊU CẦU" if score >= 75 else "CẦN LUYỆN TẬP THÊM")
            bot_comment_text = (
                f"🤖 [KẾT QUẢ ĐÁNH GIÁ ĐỘNG TÁC TỰ ĐỘNG - AI BOT]\n"
                f"⭐ Điểm số: {score:.1f}/100 ({rating_str})\n"
                f"📋 Nhận xét: {feedback}\n"
                f"🎬 Video đối chiếu: Đã đồng bộ side-by-side theo warping path DTW. Xem báo cáo chi tiết lỗi bên dưới."
            )
            comment = comment_repo.create(post_id=post.id, user_id=None, content=bot_comment_text, is_bot_evaluation=True)
            comment.score = score
            comment.detail_mistakes = result.get("report_html")
            db.commit()

        notifier.notify(sub.student_id, "score", "Đã có kết quả chấm điểm",
                        f"Bài nộp của bạn đạt {score:.1f}/100 điểm.", object_id=post.id if post else submission_id)

        return {"status": "SUCCESS", "submission_id": submission_id, "score": score}

    except Exception as e:
        error_details = traceback.format_exc()
        db.rollback()
        sub_repo.set_failed(submission_id, error_msg=str(e))
        if post:
            comment_repo.create(
                post_id=post.id, user_id=None, is_bot_evaluation=True,
                content=f"🤖 [KẾT QUẢ ĐÁNH GIÁ ĐỘNG TÁC TỰ ĐỘNG - AI BOT]\n⚠️ Chưa chấm được bài nộp: {e}",
            )
        return {"status": "FAILED", "submission_id": submission_id, "error": str(e), "traceback": error_details}
    finally:
        db.close()

@celery_app.task(bind=True, name="tasks.evaluate_submission_video")
def evaluate_submission_video(self, submission_id: int):
    """Celery background task bọc process_submission_core."""
    return process_submission_core(submission_id, task_id=self.request.id)
