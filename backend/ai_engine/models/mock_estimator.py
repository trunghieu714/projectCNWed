import hashlib
import os
from typing import Dict, Any
import numpy as np
from ..base.estimator import BasePoseEstimator
from ..pose_io import build_pose_result, read_video_meta, smpl_forward_kinematics, to_h36m

class MockPoseEstimator(BasePoseEstimator):
    """
    Mock Pose Estimator phục vụ phát triển & kiểm thử API/Frontend khi chưa có GPU/checkpoint.

    Chuyển động được sinh tất định từ nội dung file video: cùng một video luôn cho cùng
    chuỗi pose (HV nộp đúng video mẫu sẽ đạt 100 điểm), video khác nhau cho pose khác nhau.
    KHÔNG phải nhận diện pose thật - chỉ dùng khi không có estimator thật nào khả dụng.
    """

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(model_name="MockPoseModel", config=config)

    def load_model(self) -> None:
        self.is_loaded = True

    @staticmethod
    def _seed_for(video_path: str) -> int:
        h = hashlib.sha1()
        try:
            size = os.path.getsize(video_path)
            with open(video_path, "rb") as f:
                h.update(f.read(65536))
                if size > 131072:
                    f.seek(-65536, os.SEEK_END)
                    h.update(f.read(65536))
            h.update(str(size).encode())
        except OSError:
            h.update(video_path.encode("utf-8"))
        return int(h.hexdigest()[:8], 16)

    def extract_poses(self, video_path: str) -> Dict[str, Any]:
        if not self.is_loaded:
            self.load_model()

        fps, total = read_video_meta(video_path)
        sample_fps = 10.0
        duration = total / fps if total > 0 else 6.0
        n_frames = int(np.clip(round(duration * sample_fps), 30, 600))
        frame_indices = [int(round(i * fps / sample_fps)) for i in range(n_frames)]

        rng = np.random.default_rng(self._seed_for(video_path))
        t = np.linspace(0, duration, n_frames)
        # Mỗi khớp SMPL quay theo tổng 2 sóng sin với biên độ / tần số / pha ngẫu nhiên tất định
        amp = rng.uniform(0.05, 0.6, size=(24, 3, 2))
        freq = rng.uniform(0.2, 1.2, size=(24, 3, 2))
        phase = rng.uniform(0, 2 * np.pi, size=(24, 3, 2))
        aa = np.sum(amp[None] * np.sin(2 * np.pi * freq[None] * t[:, None, None, None] + phase[None]), axis=-1)
        aa[:, 0] *= 0.2  # hướng toàn thân ít thay đổi
        joints = to_h36m(smpl_forward_kinematics(aa))

        return build_pose_result(joints, fps=sample_fps, source="mock", frame_indices=frame_indices)
