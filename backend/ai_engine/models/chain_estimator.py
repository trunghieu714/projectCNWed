import logging
from typing import Any, Dict, List
from ..base.estimator import BasePoseEstimator
from ..pose_io import PoseNotAvailable

logger = logging.getLogger(__name__)

class ChainedPoseEstimator(BasePoseEstimator):
    """
    Thử lần lượt các estimator (vd: precomputed -> remote -> yolo -> mock) và dùng kết quả
    của estimator đầu tiên thành công. Kết quả ghi rõ nguồn ("source") để báo cáo minh bạch.
    """

    def __init__(self, estimators: List[BasePoseEstimator]):
        super().__init__(model_name="+".join(e.model_name for e in estimators))
        self.estimators = estimators

    def load_model(self) -> None:
        self.is_loaded = True

    def extract_poses(self, video_path: str) -> Dict[str, Any]:
        errors = []
        for est in self.estimators:
            try:
                return est.extract_poses(video_path)
            except PoseNotAvailable as e:
                errors.append(f"{est.model_name}: {e}")
                logger.info("Bỏ qua %s: %s", est.model_name, e)
        raise PoseNotAvailable("Không estimator nào trích xuất được pose. " + " | ".join(errors))
