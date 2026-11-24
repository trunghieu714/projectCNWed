import os
import tempfile

import cv2
import numpy as np

def make_video_bytes(seconds: float = 11, seed: int = 0, fps: int = 10, size=(160, 120)) -> bytes:
    """Video mp4 thật (đọc được bằng OpenCV) để vượt qua kiểm tra thời lượng tối thiểu 10 giây."""
    fd, path = tempfile.mkstemp(suffix=".mp4")
    os.close(fd)
    out = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), fps, size)
    for i in range(int(seconds * fps)):
        frame = np.full((size[1], size[0], 3), (i * 3 + seed * 40) % 255, np.uint8)
        cv2.circle(frame, (int(size[0] / 2 + 40 * np.sin(i / 5 + seed)), size[1] // 2), 10, (255, 255, 255), -1)
        out.write(frame)
    out.release()
    with open(path, "rb") as f:
        data = f.read()
    os.remove(path)
    return data
