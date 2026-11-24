import os
import time
from typing import Any, Dict, Optional
import numpy as np
from ..base.estimator import BasePoseEstimator
from ..pose_io import PoseNotAvailable, build_pose_result

class _JobsUnsupported(Exception):
    """Pose server bản cũ chưa có /jobs -> dùng /extract đồng bộ."""

class RemotePoseEstimator(BasePoseEstimator):
    """
    Gửi video tới server AI từ xa (Google Colab / PC có GPU chạy GVHMR, WHAM...) - FAQ Q5.

    Giao thức (ai_engine/remote_server/pose_server.py):
      - POST {base_url}/jobs (multipart, trường `file`) -> {"job_id"}
        GET  {base_url}/jobs/{job_id} -> {"status": PENDING|PROCESSING|COMPLETED|FAILED, "progress", "result", "error"}
        Bất đồng bộ vì GVHMR chạy vài phút, vượt giới hạn ~100s/request của Cloudflare tunnel.
      - POST {base_url}/extract: bản đồng bộ, chỉ dùng khi server chưa có /jobs.
    Kết quả: {"joints_3d": [[[x, y, z], ...], ...], "fps": 30.0, "frame_indices": [...], "source": "gvhmr:..."}
    """

    MAX_POLL_ERRORS = 5  # lỗi mạng liên tiếp cho phép khi hỏi trạng thái (tunnel chập chờn)

    def __init__(self, base_url: str = None, timeout: int = 900, api_key: Optional[str] = None,
                 poll_interval: float = 5.0, client: Any = None, config: Dict[str, Any] = None):
        super().__init__(model_name="RemotePose", config=config)
        self.base_url = (base_url or "").rstrip("/")
        self.timeout = timeout
        self.api_key = api_key
        self.poll_interval = poll_interval
        self._client = client  # cho phép test truyền TestClient

    def load_model(self) -> None:
        if not self.base_url:
            raise PoseNotAvailable("Chưa cấu hình AI_REMOTE_URL cho server pose từ xa")
        self.is_loaded = True

    def _headers(self) -> Dict[str, str]:
        return {"X-API-Key": self.api_key} if self.api_key else {}

    def _post_video(self, client, path: str, video_path: str):
        with open(video_path, "rb") as f:
            return client.post(f"{self.base_url}{path}", headers=self._headers(),
                               files={"file": (os.path.basename(video_path), f, "video/mp4")})

    def _extract_via_jobs(self, client, video_path: str) -> Dict[str, Any]:
        resp = self._post_video(client, "/jobs", video_path)
        if resp.status_code in (404, 405):
            raise _JobsUnsupported()
        resp.raise_for_status()
        job_id = resp.json()["job_id"]
        deadline = time.time() + self.timeout
        errors = 0
        while True:
            try:
                r = client.get(f"{self.base_url}/jobs/{job_id}", headers=self._headers())
                r.raise_for_status()
                job = r.json()
                errors = 0
            except Exception as e:
                errors += 1
                if errors > self.MAX_POLL_ERRORS:
                    raise PoseNotAvailable(f"Mất kết nối tới server pose từ xa: {e}") from e
                job = {"status": "PROCESSING"}
            status = job.get("status")
            if status == "COMPLETED":
                return job.get("result") or {}
            if status == "FAILED":
                raise PoseNotAvailable(f"Server pose từ xa báo lỗi: {job.get('error') or job.get('progress')}")
            if time.time() > deadline:
                raise PoseNotAvailable(f"Server pose từ xa quá {self.timeout}s chưa xong (job {job_id})")
            time.sleep(self.poll_interval)

    def _extract_sync(self, client, video_path: str) -> Dict[str, Any]:
        resp = self._post_video(client, "/extract", video_path)
        resp.raise_for_status()
        return resp.json()

    def extract_poses(self, video_path: str) -> Dict[str, Any]:
        if not self.is_loaded:
            self.load_model()
        try:
            import httpx
        except ImportError as e:
            raise PoseNotAvailable("Thiếu thư viện httpx") from e
        client = self._client or httpx.Client(timeout=min(self.timeout, 120))
        try:
            try:
                data = self._extract_via_jobs(client, video_path)
            except _JobsUnsupported:
                data = self._extract_sync(client, video_path)
        except PoseNotAvailable:
            raise
        except Exception as e:
            raise PoseNotAvailable(f"Server pose từ xa lỗi: {e}") from e
        finally:
            if self._client is None:
                client.close()
        joints = np.asarray(data.get("joints_3d", []), dtype=np.float64)
        if joints.ndim != 3 or joints.shape[-1] != 3 or len(joints) < 2:
            raise PoseNotAvailable("Server pose từ xa trả về dữ liệu không hợp lệ")
        return build_pose_result(
            joints, fps=float(data.get("fps", 30.0)), source=f"remote:{data.get('source', 'unknown')}",
            frame_indices=data.get("frame_indices"),
        )
