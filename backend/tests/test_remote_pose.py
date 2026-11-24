"""Kiểm thử estimator "remote" + pose server (chế độ GVHMR-Demo) mà không cần GPU: GVHMR-Demo được giả lập."""
import pickle

import numpy as np
import pytest
from fastapi import FastAPI, File, UploadFile
from fastapi.testclient import TestClient

from ai_engine.models.remote_estimator import RemotePoseEstimator
from ai_engine.pose_io import PoseNotAvailable, load_pose_file
from ai_engine.remote_server import pose_server

N_FRAMES = 12

def gvhmr_result(n=N_FRAMES):
    """Cấu trúc hmr4d_results.pt của GVHMR (ở đây lưu bằng pickle vì máy test không có torch)."""
    rng = np.random.default_rng(0)
    params = lambda: {"global_orient": rng.normal(0, .2, (n, 3)), "body_pose": rng.normal(0, .2, (n, 63)),
                      "betas": np.zeros((n, 10)), "transl": np.zeros((n, 3))}
    return {"smpl_params_global": params(), "smpl_params_incam": params(),
            "K_fullimg": np.tile(np.eye(3), (n, 1, 1)), "subject": "p0"}

def fake_gvhmr_app(result_path, fail=False):
    """Giả lập các endpoint của GVHMR-Demo: 503 khi model đang nạp, job PROCESSING rồi mới COMPLETED."""
    app = FastAPI()
    state = {"jobs_calls": 0, "polls": 0}

    @app.post("/api/v1/video/upload")
    async def upload(video: UploadFile = File(...)):
        await video.read()
        return {"status": "success", "video_id": "vid-1"}

    @app.post("/api/v1/jobs")
    def jobs(body: dict):
        state["jobs_calls"] += 1
        assert body["video_id"] == "vid-1" and body["static_cam"] is True
        if state["jobs_calls"] == 1:
            from fastapi import HTTPException
            raise HTTPException(503, "Model chưa được tải xong")
        return {"status": "success", "job_id": "job-1"}

    @app.get("/api/v1/jobs/{job_id}")
    def job(job_id: str):
        state["polls"] += 1
        if state["polls"] == 1:
            return {"job_id": job_id, "status": "PROCESSING", "progress": "Đang chạy ViTPose...", "result": None}
        if fail:
            return {"job_id": job_id, "status": "FAILED", "progress": "Không phát hiện được người nào", "result": None}
        return {"job_id": job_id, "status": "COMPLETED", "progress": "Hoàn thành",
                "result": {"labels": ["p0"], "result_file_paths": [str(result_path)]}}
    return app, state

@pytest.fixture
def video_file(tmp_path):
    p = tmp_path / "hv.mp4"
    p.write_bytes(b"\x00" * 64)
    return str(p)

@pytest.fixture
def gvhmr_pkl(tmp_path):
    p = tmp_path / "hmr4d_results.pkl"
    with open(p, "wb") as f:
        pickle.dump(gvhmr_result(), f)
    return p

def test_gvhmr_result_uses_global_smpl_params(gvhmr_pkl):
    joints = load_pose_file(str(gvhmr_pkl))
    assert joints.shape == (N_FRAMES, 24, 3) and np.isfinite(joints).all()

def test_gvhmr_extract_waits_for_model_and_job(gvhmr_pkl, video_file):
    app, state = fake_gvhmr_app(gvhmr_pkl)
    joints, source = pose_server.gvhmr_extract(video_file, client=TestClient(app), poll=0)
    assert joints.shape == (N_FRAMES, 24, 3)
    assert source == "job-1:p0" and state["jobs_calls"] == 2 and state["polls"] == 2

def test_gvhmr_extract_reports_failure(gvhmr_pkl, video_file):
    app, _ = fake_gvhmr_app(gvhmr_pkl, fail=True)
    with pytest.raises(pose_server.PoseServerError, match="Không phát hiện được người"):
        pose_server.gvhmr_extract(video_file, client=TestClient(app), poll=0)

def _fake_result(_path, progress=lambda _: None):
    progress("đang chạy")
    return {"joints_3d": np.zeros((N_FRAMES, 24, 3)).tolist(), "fps": 30.0,
            "frame_indices": list(range(N_FRAMES)), "source": "gvhmr:job-1:p0"}

def test_remote_estimator_job_flow_with_key(monkeypatch, video_file):
    monkeypatch.setattr(pose_server, "process_video", _fake_result)
    monkeypatch.setattr(pose_server, "SERVER_KEY", "secret")
    client = TestClient(pose_server.app)
    est = RemotePoseEstimator("http://testserver", api_key="secret", poll_interval=0.01, client=client)
    pose = est.extract_poses(video_file)
    assert pose["joints_3d"].shape == (N_FRAMES, 24, 3) and pose["source"] == "remote:gvhmr:job-1:p0"

    wrong = RemotePoseEstimator("http://testserver", api_key="nope", poll_interval=0.01, client=client)
    with pytest.raises(PoseNotAvailable):
        wrong.extract_poses(video_file)

def test_remote_estimator_surfaces_job_failure(monkeypatch, video_file):
    def boom(_path, progress=lambda _: None):
        raise pose_server.PoseServerError("GVHMR thất bại: hết bộ nhớ GPU")
    monkeypatch.setattr(pose_server, "process_video", boom)
    monkeypatch.setattr(pose_server, "SERVER_KEY", "")
    est = RemotePoseEstimator("http://testserver", poll_interval=0.01, client=TestClient(pose_server.app))
    with pytest.raises(PoseNotAvailable, match="hết bộ nhớ GPU"):
        est.extract_poses(video_file)

def test_remote_estimator_falls_back_to_sync_extract(video_file):
    old = FastAPI()  # pose server bản cũ chỉ có /extract

    @old.post("/extract")
    async def extract(file: UploadFile = File(...)):
        return _fake_result(None)

    est = RemotePoseEstimator("http://testserver", poll_interval=0.01, client=TestClient(old))
    assert est.extract_poses(video_file)["joints_3d"].shape == (N_FRAMES, 24, 3)
