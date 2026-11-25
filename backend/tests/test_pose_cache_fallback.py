"""Pose giả lập (mock) dùng khi server AI từ xa lỗi không được cache cho video HLV."""
import numpy as np

from ai_engine.base.estimator import BasePoseEstimator
from ai_engine.models.chain_estimator import ChainedPoseEstimator
from ai_engine.models.mock_estimator import MockPoseEstimator
from ai_engine.pipeline import SkillAssessmentPipeline
from ai_engine.pose_io import PoseCache, PoseNotAvailable, build_pose_result

class FlakyRemote(BasePoseEstimator):
    """Giả lập server Colab: lần đầu lỗi (GVHMR chết), các lần sau trả pose thật."""
    def __init__(self):
        super().__init__(model_name="RemotePose")
        self.calls = 0
        self.up = False

    def load_model(self):
        self.is_loaded = True

    def extract_poses(self, video_path):
        self.calls += 1
        if not self.up:
            raise PoseNotAvailable("Server pose từ xa báo lỗi: [Errno 111] Connection refused")
        return build_pose_result(np.ones((20, 24, 3)), fps=30.0, source="remote:gvhmr:job:p0")

def test_mock_fallback_is_not_cached(tmp_path):
    video = tmp_path / "coach.mp4"
    video.write_bytes(b"\x00" * 128)
    remote = FlakyRemote()
    pipe = SkillAssessmentPipeline(estimator=ChainedPoseEstimator([remote, MockPoseEstimator()]),
                                   pose_cache=PoseCache(str(tmp_path / "cache")))

    first = pipe.extract(str(video), use_cache=True)
    assert first["source"].startswith("mock")

    remote.up = True                                   # Colab chạy lại
    second = pipe.extract(str(video), use_cache=True)
    assert second["source"] == "remote:gvhmr:job:p0" and remote.calls == 2

    third = pipe.extract(str(video), use_cache=True)   # pose thật thì được cache
    assert third["source"].endswith("(cache)") and remote.calls == 2
