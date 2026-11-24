from abc import ABC, abstractmethod
from typing import Dict, Any, List
import numpy as np

class BasePoseEstimator(ABC):
    """
    Abstract Base Class cho các mô hình Pose Estimation (TCPFormer, WHAM, DSVTFormer, Neuro-Symbolic).
    Tuân thủ nguyên tắc Open/Closed Principle (OCP) và Liskov Substitution Principle (LSP).
    """

    def __init__(self, model_name: str, config: Dict[str, Any] = None):
        self.model_name = model_name
        self.config = config or {}
        self.is_loaded = False

    @abstractmethod
    def load_model(self) -> None:
        """Nạp trọng số mô hình (weights) vào RAM/VRAM GPU."""
        pass

    @abstractmethod
    def extract_poses(self, video_path: str) -> Dict[str, Any]:
        """
        Trích xuất chuỗi khung xương từ file video.

        Returns:
            Dict chứa:
                - "keypoints_3d": np.ndarray shape (N_frames, N_joints, 3)
                - "joint_angles": np.ndarray (danh sách các góc quan trọng theo frame)
                - "fps": float
                - "total_frames": int
        """
        pass
