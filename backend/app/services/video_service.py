"""Lưu trữ & xử lý file media: kiểm tra định dạng / dung lượng / thời lượng, ghép 2 góc quay, thumbnail."""
import os
import shutil
import uuid
from typing import Optional

from ..core.config import settings
from ..core.errors import ApiError
from ..core.video_transcoder import ensure_web_compatible_video, merge_side_by_side

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

def to_url(path: Optional[str]) -> Optional[str]:
    """Đường dẫn file -> URL tương đối phục vụ bởi route /storage."""
    if not path:
        return path
    url = path.replace("\\", "/")
    if url.startswith("./"):
        url = url[2:]
    return url if url.startswith(("/", "http://", "https://")) else "/" + url

def to_fs(url: Optional[str]) -> str:
    """URL /storage/... -> đường dẫn file trên đĩa."""
    if not url:
        return ""
    if os.path.exists(url):
        return url
    clean = url.lstrip("/")
    if os.path.exists(clean):
        return clean
    app_path = os.path.join("/app", clean)
    return app_path if os.path.exists(app_path) else clean

def _upload_size(upload) -> int:
    f = upload.file
    f.seek(0, os.SEEK_END)
    size = f.tell()
    f.seek(0)
    return size

def probe_duration(path: str) -> Optional[float]:
    """Thời lượng video (giây) qua OpenCV; None nếu không đọc được."""
    try:
        import cv2
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            return None
        fps = cap.get(cv2.CAP_PROP_FPS) or 0
        frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
        duration = frames / fps if fps > 0 and frames > 0 else 0.0
        if duration <= 0:  # webm/mkv đôi khi không có số frame -> nhảy tới cuối file
            cap.set(cv2.CAP_PROP_POS_AVI_RATIO, 1)
            duration = (cap.get(cv2.CAP_PROP_POS_MSEC) or 0) / 1000.0
        cap.release()
        return duration if duration > 0 else None
    except Exception:
        return None

def save_video_upload(upload, prefix: str, min_seconds: Optional[float] = None) -> str:
    """
    Lưu video upload -> URL. Mã lỗi theo đặc tả:
    1006 dung lượng quá lớn, 1007 upload thất bại / sai định dạng, 1004 thời lượng quá ngắn.
    """
    filename = upload.filename or ""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in settings.allowed_extension_list:
        raise ApiError("1007", f"Định dạng video {ext or '(không rõ)'} không được hỗ trợ. Chỉ chấp nhận: {settings.ALLOWED_EXTENSIONS}")
    if _upload_size(upload) > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise ApiError("1006", f"Dung lượng video vượt quá {settings.MAX_UPLOAD_SIZE_MB}MB.")

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    path = os.path.join(settings.UPLOAD_DIR, f"{prefix}_{uuid.uuid4().hex[:12]}{ext}")
    with open(path, "wb") as out:
        shutil.copyfileobj(upload.file, out)

    limit = settings.MIN_VIDEO_SECONDS if min_seconds is None else min_seconds
    duration = probe_duration(path)
    if duration is None:
        os.remove(path)
        raise ApiError("1007", "Không đọc được file video. Vui lòng chọn video khác.")
    if duration + 0.05 < limit:
        os.remove(path)
        raise ApiError("1004", f"Thời lượng video quá ngắn ({duration:.1f}s). Tối thiểu {limit:.0f} giây.")

    ensure_web_compatible_video(path)
    return to_url(path)

def save_image_upload(upload, prefix: str, directory: Optional[str] = None) -> str:
    ext = os.path.splitext(upload.filename or "")[1].lower()
    if ext not in IMAGE_EXTENSIONS:
        raise ApiError("1007", "File ảnh không đúng định dạng (jpg, png, webp, gif).")
    if _upload_size(upload) > settings.MAX_AVATAR_SIZE_MB * 1024 * 1024:
        raise ApiError("1006", f"Dung lượng ảnh vượt quá {settings.MAX_AVATAR_SIZE_MB}MB.")
    directory = directory or settings.AVATAR_DIR
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, f"{prefix}_{uuid.uuid4().hex[:12]}{ext}")
    with open(path, "wb") as out:
        shutil.copyfileobj(upload.file, out)
    return to_url(path)

def merge_videos(left_url: str, right_url: str, prefix: str) -> Optional[str]:
    """Ghép video trái | phải thành 1 video (FFmpeg, dự phòng OpenCV) - Slide 25, FAQ Q6."""
    left, right = to_fs(left_url), to_fs(right_url)
    out = os.path.join(settings.UPLOAD_DIR, f"{prefix}_fused_{uuid.uuid4().hex[:8]}.mp4")
    try:
        merged = merge_side_by_side(left, right, out)
        if not merged:
            from ai_engine.visualizers.video_renderer import FusedVideoRenderer
            merged = FusedVideoRenderer().merge_two_videos(left, right, out)
        return to_url(merged)
    except Exception:
        return None

def make_thumbnail(video_url: Optional[str]) -> Optional[str]:
    if not video_url:
        return None
    try:
        import cv2
        src = to_fs(video_url)
        cap = cv2.VideoCapture(src)
        frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
        if frames > 10:
            cap.set(cv2.CAP_PROP_POS_FRAMES, min(int(frames * 0.1), 30))
        ok, frame = cap.read()
        cap.release()
        if not ok:
            return None
        out = os.path.splitext(src)[0] + "_thumb.jpg"
        h, w = frame.shape[:2]
        scale = 480.0 / max(w, 1)
        if scale < 1:
            frame = cv2.resize(frame, (480, int(h * scale)))
        cv2.imwrite(out, frame)
        return to_url(out)
    except Exception:
        return None
