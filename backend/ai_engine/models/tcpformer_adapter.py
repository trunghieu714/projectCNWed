import logging
import os
from typing import Dict, Any
from ..base.estimator import BasePoseEstimator
from ..pose_io import PoseNotAvailable

logger = logging.getLogger(__name__)

class TCPFormerAdapter(BasePoseEstimator):
    """
    Adapter Pattern bọc TCPFormer (Temporal Correlation with Implicit Pose Proxy - Slide 9).

    TCPFormer là mô hình lifting 2D -> 3D (đầu vào: chuỗi 81/243 frame pose 2D H36M). Mã nguồn
    mạng và cách nạp checkpoint có trong notebook Colab ở Slide 9 (MemoryInducedTransformer,
    checkpoint TCPFormer_ap3d_81.pth.tr). Thành viên AI Lead cắm kiến trúc đó vào `self.model`.

    Khi chưa có checkpoint, adapter báo PoseNotAvailable để ChainedPoseEstimator chuyển sang
    estimator khác - KHÔNG tự sinh dữ liệu giả.
    """

    def __init__(self, weights_path: str = "checkpoints/tcpformer.pth", config: Dict[str, Any] = None):
        super().__init__(model_name="TCPFormer", config=config)
        self.weights_path = weights_path
        self.model = None

    def load_model(self) -> None:
        if not os.path.exists(self.weights_path):
            raise PoseNotAvailable(f"Chưa có checkpoint TCPFormer tại {self.weights_path}")
        # import torch
        # self.model = MemoryInducedTransformer(n_layers=16, dim_in=3, dim_feat=128, n_frames=81)
        # self.model.load_state_dict(torch.load(self.weights_path, map_location="cpu")["model"])
        # self.model.eval()
        self.is_loaded = True

    def extract_poses(self, video_path: str) -> Dict[str, Any]:
        if not self.is_loaded:
            self.load_model()
        if self.model is None:
            raise PoseNotAvailable("Kiến trúc TCPFormer chưa được tích hợp vào adapter (xem notebook Slide 9)")
        raise PoseNotAvailable("TCPFormer cần chuỗi pose 2D đầu vào - hãy ghép sau YoloPoseEstimator")
