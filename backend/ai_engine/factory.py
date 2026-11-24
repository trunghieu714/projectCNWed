from typing import Any, Dict, List, Optional
from .base.estimator import BasePoseEstimator
from .base.scorer import BaseScorer
from .base.visualizer import BaseVisualizer
from .models.mock_estimator import MockPoseEstimator
from .models.tcpformer_adapter import TCPFormerAdapter
from .models.precomputed_estimator import PrecomputedPoseEstimator
from .models.yolo_estimator import YoloPoseEstimator
from .models.remote_estimator import RemotePoseEstimator
from .models.chain_estimator import ChainedPoseEstimator
from .scorers.dtw_scorer import FastDTWScorer
from .scorers.pa_mpjpe_dtw_scorer import PAMPJPEDTWScorer
from .visualizers.video_renderer import FusedVideoRenderer

class AIEngineFactory:
    """
    Factory Pattern: Đóng gói việc khởi tạo các đối tượng Estimator, Scorer và Visualizer.
    Giúp tầng Backend Service không cần biết chi tiết khởi tạo bên trong.
    """

    @staticmethod
    def create_estimator(model_type: str = "mock", config: Dict[str, Any] = None) -> BasePoseEstimator:
        config = config or {}
        types = [t.strip().lower() for t in model_type.split(",") if t.strip()]
        if len(types) > 1:
            return ChainedPoseEstimator([AIEngineFactory.create_estimator(t, config) for t in types])
        model_type = types[0] if types else "mock"
        if model_type == "mock":
            return MockPoseEstimator(config=config)
        if model_type in ("precomputed", "wham", "gvhmr", "pkl"):
            return PrecomputedPoseEstimator(config=config)
        if model_type == "yolo":
            return YoloPoseEstimator(weights=config.get("yolo_weights", "yolo26x-pose.pt"), config=config)
        if model_type == "remote":
            return RemotePoseEstimator(base_url=config.get("remote_url"), timeout=config.get("remote_timeout", 900), config=config)
        if model_type == "tcpformer":
            return TCPFormerAdapter(config=config)
        raise ValueError(f"Không hỗ trợ mô hình: {model_type}")

    @staticmethod
    def create_scorer(scorer_type: str = "dtw", **kwargs) -> BaseScorer:
        scorer_type = scorer_type.lower()
        if scorer_type == "dtw":
            return FastDTWScorer(angle_tolerance=kwargs.get("angle_tolerance", 15.0))
        if scorer_type in ("pa_mpjpe_dtw", "pa-mpjpe", "pampjpe"):
            return PAMPJPEDTWScorer(
                window_ratio=kwargs.get("window_ratio", 0.1),
                tolerance=kwargs.get("tolerance", 0.12),
                max_error=kwargs.get("max_error", 0.45),
            )
        raise ValueError(f"Không hỗ trợ scorer: {scorer_type}")

    @staticmethod
    def create_visualizer(vis_type: str = "fused_video", **kwargs) -> BaseVisualizer:
        if vis_type == "fused_video":
            return FusedVideoRenderer(target_fps=kwargs.get("fps", 25))
        raise ValueError(f"Không hỗ trợ visualizer: {vis_type}")

    @staticmethod
    def create_pipeline_from_settings(settings: Any):
        """Khởi tạo pipeline theo cấu hình .env (AI_ESTIMATOR_TYPE, AI_SCORER_TYPE...)."""
        from .pipeline import SkillAssessmentPipeline
        from .pose_io import PoseCache
        config = {
            "remote_url": getattr(settings, "AI_REMOTE_URL", None),
            "remote_timeout": getattr(settings, "AI_REMOTE_TIMEOUT", 900),
            "yolo_weights": getattr(settings, "YOLO_POSE_WEIGHTS", "yolo26x-pose.pt"),
            "search_dirs": [getattr(settings, "POSE_CACHE_DIR", "storage/pose_cache")],
        }
        estimator = AIEngineFactory.create_estimator(getattr(settings, "AI_ESTIMATOR_TYPE", "mock"), config)
        scorer = AIEngineFactory.create_scorer(
            getattr(settings, "AI_SCORER_TYPE", "pa_mpjpe_dtw"),
            window_ratio=getattr(settings, "DTW_WINDOW_RATIO", 0.1),
            tolerance=getattr(settings, "SCORE_ERROR_TOLERANCE", 0.12),
            max_error=getattr(settings, "SCORE_MAX_ERROR", 0.45),
        )
        visualizer = AIEngineFactory.create_visualizer(getattr(settings, "AI_VISUALIZER_TYPE", "fused_video"))
        return SkillAssessmentPipeline(
            estimator=estimator, scorer=scorer, visualizer=visualizer,
            pose_cache=PoseCache(getattr(settings, "POSE_CACHE_DIR", "storage/pose_cache")),
            calibration_path=getattr(settings, "AI_CAMERA_CALIB_PATH", None),
        )
