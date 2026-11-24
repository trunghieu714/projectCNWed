import glob
import os
from typing import Any, Dict, List, Optional
from ..base.estimator import BasePoseEstimator
from ..pose_io import PoseNotAvailable, build_pose_result, load_pose_file, read_video_meta

POSE_EXTENSIONS = (".pkl", ".pt", ".npz", ".npy", ".json")

class PrecomputedPoseEstimator(BasePoseEstimator):
    """
    Đọc pose 3D đã được tính sẵn bởi WHAM / GVHMR / TCPFormer (chạy trên Colab hoặc PC có GPU).

    Quy ước tìm file cho video `abc.mp4`:
      - cùng thư mục: abc.pkl, abc_wham.pkl, abc.pt, abc.npz, abc.npy, abc.json
      - thư mục con cùng tên: abc/*.pkl (đầu ra mặc định của demo WHAM/GVHMR: wham_output.pkl, hmr4d_results.pt)
      - các thư mục bổ sung trong config["search_dirs"]
    """

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(model_name="PrecomputedPose", config=config)
        self.search_dirs: List[str] = list((config or {}).get("search_dirs", []))

    def load_model(self) -> None:
        self.is_loaded = True

    def find_pose_file(self, video_path: str) -> Optional[str]:
        base, _ = os.path.splitext(video_path)
        stem = os.path.basename(base)
        dirs = [os.path.dirname(video_path)] + self.search_dirs
        candidates = []
        for d in dirs:
            for ext in POSE_EXTENSIONS:
                candidates += [os.path.join(d, stem + ext), os.path.join(d, f"{stem}_wham{ext}"),
                               os.path.join(d, f"{stem}_gvhmr{ext}"), os.path.join(d, f"{stem}_pose3d{ext}")]
            sub = os.path.join(d, stem)
            if os.path.isdir(sub):
                for ext in POSE_EXTENSIONS:
                    candidates += sorted(glob.glob(os.path.join(sub, "**", f"*{ext}"), recursive=True))
        for c in candidates:
            if os.path.isfile(c):
                return c
        return None

    def extract_poses(self, video_path: str) -> Dict[str, Any]:
        pose_file = self.find_pose_file(video_path)
        if not pose_file:
            raise PoseNotAvailable(f"Chưa có file pose tính sẵn cho {os.path.basename(video_path)}")
        joints = load_pose_file(pose_file)
        video_fps, total = read_video_meta(video_path)
        # Mô hình monocular xuất 1 pose / frame video
        fps = video_fps if total == 0 or abs(total - len(joints)) <= max(5, 0.1 * total) else len(joints) / max(total / video_fps, 1e-6)
        return build_pose_result(joints, fps=fps, source=f"precomputed:{os.path.basename(pose_file)}")
