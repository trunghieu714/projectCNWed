import os
from typing import Any, Dict
import numpy as np
from ..base.estimator import BasePoseEstimator
from ..pose_io import PoseNotAvailable, build_pose_result

class RemotePoseEstimator(BasePoseEstimator):
    """
    Gửi video tới server AI từ xa (Google Colab / PC có GPU chạy WHAM, GVHMR...) - FAQ Q5.

    Server cần cung cấp `POST {base_url}/extract` (multipart, trường `file`) và trả về JSON:
        {"joints_3d": [[[x, y, z], ...], ...], "fps": 30.0, "source": "gvhmr"}
    Xem server mẫu ở ai_engine/remote_server/pose_server.py.
    """

    def __init__(self, base_url: str = None, timeout: int = 900, config: Dict[str, Any] = None):
        super().__init__(model_name="RemotePose", config=config)
        self.base_url = (base_url or "").rstrip("/")
        self.timeout = timeout

    def load_model(self) -> None:
        if not self.base_url:
            raise PoseNotAvailable("Chưa cấu hình AI_REMOTE_URL cho server pose từ xa")
        self.is_loaded = True

    def extract_poses(self, video_path: str) -> Dict[str, Any]:
        if not self.is_loaded:
            self.load_model()
        try:
            import httpx
        except ImportError as e:
            raise PoseNotAvailable("Thiếu thư viện httpx") from e
        try:
            with open(video_path, "rb") as f:
                resp = httpx.post(
                    f"{self.base_url}/extract",
                    files={"file": (os.path.basename(video_path), f, "video/mp4")},
                    timeout=self.timeout,
                )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            raise PoseNotAvailable(f"Server pose từ xa lỗi: {e}") from e
        joints = np.asarray(data.get("joints_3d", []), dtype=np.float64)
        if joints.ndim != 3 or joints.shape[-1] != 3 or len(joints) < 2:
            raise PoseNotAvailable("Server pose từ xa trả về dữ liệu không hợp lệ")
        return build_pose_result(
            joints, fps=float(data.get("fps", 30.0)), source=f"remote:{data.get('source', 'unknown')}",
            frame_indices=data.get("frame_indices"),
        )
