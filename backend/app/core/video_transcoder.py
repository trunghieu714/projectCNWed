import os
import shutil
import subprocess
import logging
from functools import lru_cache
from typing import Optional

logger = logging.getLogger(__name__)

@lru_cache(maxsize=1)
def ffmpeg_binary() -> Optional[str]:
    """Đường dẫn FFmpeg nếu máy có cài (FFMPEG_BINARY trong .env hoặc trong PATH)."""
    from .config import settings
    return shutil.which(settings.FFMPEG_BINARY) or (settings.FFMPEG_BINARY if os.path.isfile(settings.FFMPEG_BINARY) else None)

def _run(cmd, timeout: int = 300) -> bool:
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
        if res.returncode != 0:
            logger.warning("ffmpeg lỗi: %s", res.stderr.decode("utf-8", errors="ignore")[-500:])
        return res.returncode == 0
    except Exception as e:
        logger.error("Không chạy được ffmpeg: %s", e)
        return False

def ensure_web_compatible_video(video_path: str) -> str:
    """
    Sử dụng ffmpeg để chuẩn hóa video sang chuẩn H.264 (avc1) + yuv420p + faststart.
    Đảm bảo các trình duyệt (Chrome, Safari, Edge, Firefox) có thể stream và phát ngay.
    Bỏ qua (giữ nguyên file) nếu máy chưa cài ffmpeg.
    """
    ffmpeg = ffmpeg_binary()
    if not ffmpeg or not os.path.exists(video_path):
        return video_path

    temp_output = video_path + ".h264_temp.mp4"
    ok = _run([ffmpeg, "-y", "-i", video_path, "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
               "-pix_fmt", "yuv420p", "-movflags", "+faststart", temp_output], timeout=300)
    if ok and os.path.exists(temp_output) and os.path.getsize(temp_output) > 0:
        shutil.move(temp_output, video_path)
    elif os.path.exists(temp_output):
        os.remove(temp_output)
    return video_path

def merge_side_by_side(left_path: str, right_path: str, output_path: str) -> Optional[str]:
    """
    FAQ Q6: Service Server dùng FFmpeg tự ghép 2 video (trái | phải) thành một.
    Hai video được đưa về cùng chiều cao 480px; độ dài theo video ngắn hơn.
    Trả về None nếu không có ffmpeg hoặc ghép thất bại (caller dùng OpenCV dự phòng).
    """
    ffmpeg = ffmpeg_binary()
    if not ffmpeg:
        return None
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    filter_graph = (
        "[0:v]scale=-2:480,setsar=1[l];[1:v]scale=-2:480,setsar=1[r];"
        "[l][r]hstack=inputs=2:shortest=1[v]"
    )
    ok = _run([ffmpeg, "-y", "-i", left_path, "-i", right_path, "-filter_complex", filter_graph,
               "-map", "[v]", "-map", "0:a?", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
               "-pix_fmt", "yuv420p", "-movflags", "+faststart", output_path], timeout=600)
    return output_path if ok and os.path.exists(output_path) else None
