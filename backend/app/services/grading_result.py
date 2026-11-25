"""
Gói kết quả chấm điểm dạng file zip (Slide 8: "software/web local hiển thị HTML trên PC cũng như gọi API gửi file zip").

Cấu trúc result.zip:
    report.html   báo cáo chi tiết lỗi (tab Bên Trái / Bên Phải) - cũng là detail_mistakes của bình luận điểm
    result.json   {"score": 0-100, "summary": "...", ...chi tiết từng góc quay, warping path, đoạn lỗi}
    fused.mp4     (tùy chọn) video ghép HLV - HV theo warping path

- Pipeline chấm trong server tự đóng gói sau khi chấm (build_result_zip).
- Phần mềm chấm bên ngoài (PC có GPU / Colab) gửi zip lên bằng API set_grading_result (apply_result_zip).
"""
import io
import json
import os
import zipfile
from typing import Any, Dict, Optional, Tuple

from sqlalchemy.orm import Session

from ai_engine.visualizers.html_report import extract_viewer_data, write_skeleton_json

from ..core.config import settings
from ..core.errors import ApiError, param_invalid
from ..models.entities import Comment, SocialPost, Submission, SubmissionStatus
from .notification_service import NotificationService
from .video_service import to_url

REPORT_NAME, RESULT_NAME, VIDEO_NAME, ZIP_NAME = "report.html", "result.json", "fused.mp4", "result.zip"
SKELETON_NAME = "skeleton3d.json"   # dữ liệu khung xương 3D cho trang web (ai_engine/visualizers/skeleton_3d.py)
MAX_ZIP_BYTES = 200 * 1024 * 1024        # file zip gửi lên
MAX_MEMBER_BYTES = {REPORT_NAME: 20 * 1024 * 1024, RESULT_NAME: 20 * 1024 * 1024, VIDEO_NAME: 300 * 1024 * 1024}

def result_dir(submission_id: int) -> str:
    return os.path.join(settings.OUTPUT_DIR, f"sub_{submission_id}")

def zip_path(submission_id: int) -> str:
    return os.path.join(result_dir(submission_id), ZIP_NAME)

def build_result_zip(submission_id: int, report_html: Optional[str], result: Dict[str, Any],
                     fused_video_path: Optional[str] = None) -> str:
    """Ghi result.zip vào thư mục kết quả của bài nộp, trả về đường dẫn file."""
    os.makedirs(result_dir(submission_id), exist_ok=True)
    path = zip_path(submission_id)
    tmp = path + ".tmp"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(REPORT_NAME, report_html or "")
        zf.writestr(RESULT_NAME, json.dumps(result, ensure_ascii=False, indent=1, default=str))
        if fused_video_path and os.path.isfile(fused_video_path):
            zf.write(fused_video_path, VIDEO_NAME, compress_type=zipfile.ZIP_STORED)
    os.replace(tmp, path)
    return path

def read_result_zip(data: bytes) -> Tuple[str, Dict[str, Any], Optional[bytes]]:
    """Kiểm tra và đọc zip gửi lên -> (report_html, result, video_bytes). Không giải nén ra đĩa."""
    if len(data) > MAX_ZIP_BYTES:
        raise ApiError("1006", "File zip vượt quá dung lượng cho phép.")
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as e:
        raise param_invalid("File gửi lên không phải file zip hợp lệ.") from e
    members = {i.filename: i for i in zf.infolist()}
    for name in (REPORT_NAME, RESULT_NAME):
        if name not in members:
            raise param_invalid(f"File zip thiếu {name}.")
    for name, limit in MAX_MEMBER_BYTES.items():
        if name in members and members[name].file_size > limit:
            raise ApiError("1006", f"{name} trong file zip quá lớn.")
    try:
        report_html = zf.read(REPORT_NAME).decode("utf-8")
        result = json.loads(zf.read(RESULT_NAME).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise param_invalid("report.html / result.json không đọc được (cần UTF-8, JSON hợp lệ).") from e
    score = result.get("score") if isinstance(result, dict) else None
    if not isinstance(score, (int, float)) or isinstance(score, bool) or not 0 <= score <= 100:
        raise param_invalid("result.json cần trường score là số từ 0 đến 100.")
    video = zf.read(VIDEO_NAME) if VIDEO_NAME in members else None
    return report_html, result, video

def score_comment_text(score: float, feedback: str) -> str:
    rating = "XUẤT SẮC" if score >= 90 else ("ĐẠT YÊU CẦU" if score >= 75 else "CẦN LUYỆN TẬP THÊM")
    return (
        f"🤖 [KẾT QUẢ ĐÁNH GIÁ ĐỘNG TÁC TỰ ĐỘNG - AI BOT]\n"
        f"⭐ Điểm số: {score:.1f}/100 ({rating})\n"
        f"📋 Nhận xét: {feedback}\n"
        f"🎬 Video đối chiếu: Đã đồng bộ side-by-side theo warping path DTW. Xem báo cáo chi tiết lỗi bên dưới."
    )

def apply_result_zip(db: Session, post: SocialPost, data: bytes) -> Dict[str, Any]:
    """
    Nhận kết quả chấm từ phần mềm bên ngoài: lưu zip, cập nhật bài nộp, thay bình luận điểm cũ của bot
    bằng bình luận mới (score + detail_mistakes = report.html) và báo cho HV.
    """
    sub: Optional[Submission] = post.submission
    if not sub:
        raise param_invalid("Bài viết này không phải bài nộp của học viên.")
    report_html, result, video = read_result_zip(data)
    score = float(result["score"])
    feedback = str(result.get("summary") or result.get("feedback") or "Kết quả do phần mềm chấm gửi lên.")[:2000]

    folder = result_dir(sub.id)
    os.makedirs(folder, exist_ok=True)
    with open(zip_path(sub.id), "wb") as f:
        f.write(data)
    with open(os.path.join(folder, REPORT_NAME), "w", encoding="utf-8") as f:
        f.write(report_html)
    # Khung xương 3D cho trang web lấy từ report.html gửi lên; không có thì bỏ file của lần chấm trước
    skeleton = os.path.join(folder, SKELETON_NAME)
    if not write_skeleton_json(skeleton, extract_viewer_data(report_html)) and os.path.exists(skeleton):
        os.remove(skeleton)
    if video:
        with open(os.path.join(folder, VIDEO_NAME), "wb") as f:
            f.write(video)
        sub.fused_video_url = to_url(os.path.join(folder, VIDEO_NAME))

    sub.status = SubmissionStatus.COMPLETED
    sub.score = score
    sub.feedback_text = feedback
    sub.error_message = None
    sub.report_html_url = to_url(os.path.join(folder, REPORT_NAME))
    sub.result_json = json.dumps(result, ensure_ascii=False, default=str)

    db.query(Comment).filter(Comment.post_id == post.id, Comment.is_bot_evaluation.is_(True)).delete()
    comment = Comment(post_id=post.id, user_id=None, is_bot_evaluation=True,
                      content=score_comment_text(score, feedback), score=score, detail_mistakes=report_html)
    db.add(comment)
    db.commit()
    NotificationService(db).notify(sub.student_id, "score", "Đã có kết quả chấm điểm",
                                   f"Bài nộp của bạn đạt {score:.1f}/100 điểm.", object_id=post.id)
    return {"id": post.id, "submission_id": sub.id, "score": score, "comment_id": comment.id,
            "url": to_url(zip_path(sub.id))}

def ensure_result_zip(sub: Submission) -> Optional[str]:
    """Đường dẫn result.zip của bài nộp; bài chấm trước khi có tính năng này thì đóng gói lại từ dữ liệu đã lưu."""
    path = zip_path(sub.id)
    if os.path.isfile(path):
        return path
    if sub.status != SubmissionStatus.COMPLETED:
        return None
    report = ""
    report_file = os.path.join(result_dir(sub.id), REPORT_NAME)
    if os.path.isfile(report_file):
        with open(report_file, encoding="utf-8") as f:
            report = f.read()
    result = json.loads(sub.result_json) if sub.result_json else {}
    result.setdefault("score", sub.score)
    result.setdefault("summary", sub.feedback_text)
    fused = sub.fused_video_url.lstrip("/") if sub.fused_video_url else None
    return build_result_zip(sub.id, report, result, fused)
