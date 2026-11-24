"""
Server trích xuất pose 3D chạy trên Google Colab / PC có GPU (FAQ Q5: được host pipeline AI lên Colab).

Backend (estimator "remote", AI_REMOTE_URL) gửi video tới đây và nhận về khớp 3D (N, J, 3).
Chọn cách trích xuất bằng biến môi trường POSE_BACKEND:

  gvhmr_api : chuyển tiếp tới server FastAPI của GVHMR-Demo (github.com/doantrunghieu08/GVHMR-Demo)
              chạy cùng máy: upload -> tạo job -> đợi -> đọc hmr4d_results.pt -> FK SMPL ra 24 khớp.
              GVHMR_URL (mặc định http://127.0.0.1:8000), GVHMR_API_KEY, GVHMR_DIR (thư mục repo,
              để giải đường dẫn tương đối của file .pt), GVHMR_STATIC_CAM (1 = camera đứng yên).
  command   : chạy lệnh POSE_COMMAND (vd WHAM: "python demo.py --video {video} --output_pth {out_dir} --save_pkl")
              rồi đọc file kết quả bằng ai_engine.pose_io.
  yolo      : YOLO pose (ultralytics) - mặc định khi không đặt gì.

API:
  POST /jobs (multipart `file`) -> {"job_id"};  GET /jobs/{job_id} -> {"status", "progress", "result", "error"}
  POST /extract (multipart `file`) -> kết quả ngay (đồng bộ, chỉ hợp với video ngắn khi đi qua tunnel)
Nếu đặt POSE_SERVER_KEY thì mọi request phải có header X-API-Key trùng khớp.

Cách dựng trên Colab: xem colab/MotionAI_Colab_GPU_Server.ipynb.
"""
import glob
import os
import shlex
import subprocess
import tempfile
import threading
import time
import uuid
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Dict, Optional, Tuple

import numpy as np
import uvicorn
from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool

from ai_engine.pose_io import PoseNotAvailable, load_pose_file, read_video_meta

POSE_COMMAND = os.environ.get("POSE_COMMAND", "").strip()
POSE_BACKEND = (os.environ.get("POSE_BACKEND", "").strip().lower()
                or ("command" if POSE_COMMAND else "yolo"))
POSE_SOURCE = os.environ.get("POSE_SOURCE", "").strip() or {
    "gvhmr_api": "gvhmr", "command": "gvhmr" if "gvhmr" in POSE_COMMAND.lower() else "wham",
}.get(POSE_BACKEND, "yolo")
TIMEOUT = int(os.environ.get("POSE_TIMEOUT", "1200"))
SERVER_KEY = os.environ.get("POSE_SERVER_KEY", "").strip()
GVHMR_URL = os.environ.get("GVHMR_URL", "http://127.0.0.1:8000").rstrip("/")
GVHMR_API_KEY = os.environ.get("GVHMR_API_KEY", "")
GVHMR_DIR = os.environ.get("GVHMR_DIR", "/content/GVHMR")
GVHMR_STATIC_CAM = os.environ.get("GVHMR_STATIC_CAM", "1") != "0"
GVHMR_POLL = float(os.environ.get("GVHMR_POLL", "3"))
RESULT_PATTERNS = ("**/*.pkl", "**/*.pt", "**/*.npz", "**/*.npy", "**/*.json")
MAX_JOBS_KEPT = 200

class PoseServerError(Exception):
    pass

def require_key(x_api_key: Optional[str] = Header(default=None)):
    if SERVER_KEY and x_api_key != SERVER_KEY:
        raise HTTPException(401, "Sai hoặc thiếu X-API-Key")

app = FastAPI(title="Pose 3D Extraction Server")

# ---------------------------------------------------------------------------------------------- GVHMR-Demo
def _gvhmr_check(resp, what: str) -> dict:
    if resp.status_code >= 400:
        raise PoseServerError(f"GVHMR {what} lỗi {resp.status_code}: {resp.text[:500]}")
    return resp.json()

def gvhmr_extract(video_path: str, client=None, progress: Callable[[str], None] = lambda _: None,
                  timeout: int = TIMEOUT, poll: float = GVHMR_POLL) -> Tuple[np.ndarray, str]:
    """Chạy một video qua API của GVHMR-Demo, trả về (khớp 3D, nhãn nguồn)."""
    import httpx
    own = client is None
    client = client or httpx.Client(base_url=GVHMR_URL, timeout=120)
    headers = {"X-API-Key": GVHMR_API_KEY}
    deadline = time.time() + timeout
    try:
        progress("GVHMR: đang tải video lên")
        with open(video_path, "rb") as f:
            up = _gvhmr_check(client.post("/api/v1/video/upload", headers=headers,
                                          files={"video": (os.path.basename(video_path), f, "video/mp4")}), "upload")
        body = {"video_id": up["video_id"], "static_cam": GVHMR_STATIC_CAM, "use_dpvo": False}
        while True:  # 503 = checkpoint vẫn đang được nạp vào GPU
            r = client.post("/api/v1/jobs", headers=headers, json=body)
            if r.status_code != 503 or time.time() > deadline:
                break
            progress("GVHMR: đợi mô hình nạp xong vào GPU")
            time.sleep(poll)
        job_id = _gvhmr_check(r, "tạo job")["job_id"]
        while True:
            job = _gvhmr_check(client.get(f"/api/v1/jobs/{job_id}", headers=headers), "trạng thái job")
            if job.get("status") == "COMPLETED":
                break
            if job.get("status") == "FAILED":
                raise PoseServerError(f"GVHMR thất bại: {job.get('progress')}")
            if time.time() > deadline:
                raise PoseServerError(f"GVHMR quá {timeout}s chưa xong")
            progress(f"GVHMR: {job.get('progress') or job.get('status')}")
            time.sleep(poll)
    finally:
        if own:
            client.close()
    result = job.get("result") or {}
    paths = result.get("result_file_paths") or [result.get("result_file_path")]
    if not paths or not paths[0]:
        raise PoseServerError("GVHMR xong nhưng không trả về file kết quả")
    # Track "p0" là người xuất hiện lâu nhất trong video (Tracker.get_n_tracks sắp theo độ dài track)
    path = paths[0] if os.path.isabs(paths[0]) else os.path.join(GVHMR_DIR, paths[0])
    try:
        joints = load_pose_file(path)
    except (PoseNotAvailable, OSError) as e:
        raise PoseServerError(f"Không đọc được kết quả GVHMR {path}: {e}") from e
    label = (result.get("labels") or ["p0"])[0]
    return joints, f"{job_id}:{label}"

# ---------------------------------------------------------------------------------------------- lệnh / YOLO
def _run_command(video_path: str, out_dir: str) -> Tuple[np.ndarray, str]:
    cmd = POSE_COMMAND.format(video=shlex.quote(video_path), out_dir=shlex.quote(out_dir))
    res = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=TIMEOUT)
    if res.returncode != 0:
        raise PoseServerError(f"Lệnh mô hình lỗi: {res.stderr.decode('utf-8', 'ignore')[-1500:]}")
    started = os.path.getmtime(video_path)
    files = []
    for pattern in RESULT_PATTERNS:
        files += [f for f in glob.glob(os.path.join(out_dir, pattern), recursive=True) if os.path.getmtime(f) >= started - 1]
    for f in sorted(files, key=os.path.getmtime, reverse=True):
        try:
            return load_pose_file(f), os.path.basename(f)
        except PoseNotAvailable:
            continue
    raise PoseServerError("Mô hình chạy xong nhưng không tìm thấy file pose 3D trong thư mục kết quả.")

def process_video(video_path: str, progress: Callable[[str], None] = lambda _: None) -> Dict:
    t0 = time.time()
    fps, _ = read_video_meta(video_path)
    if POSE_BACKEND == "gvhmr_api":
        joints, result_file = gvhmr_extract(video_path, progress=progress)
        frame_indices = list(range(len(joints)))
    elif POSE_BACKEND == "command":
        progress("Đang chạy POSE_COMMAND")
        joints, result_file = _run_command(video_path, os.path.join(os.path.dirname(video_path), "out"))
        frame_indices = list(range(len(joints)))
    else:
        from ai_engine.models.yolo_estimator import YoloPoseEstimator
        progress("Đang chạy YOLO pose")
        try:
            pose = YoloPoseEstimator(weights=os.environ.get("YOLO_POSE_WEIGHTS", "yolo26x-pose.pt")).extract_poses(video_path)
        except PoseNotAvailable as e:
            raise PoseServerError(str(e)) from e
        joints, fps, frame_indices, result_file = pose["joints_3d"], pose["fps"], pose["frame_indices"], "yolo"
    return {
        "joints_3d": np.asarray(joints).round(5).tolist(),
        "fps": fps,
        "frame_indices": frame_indices,
        "source": f"{POSE_SOURCE}:{result_file}",
        "seconds": round(time.time() - t0, 1),
    }

async def _save_upload(file: UploadFile) -> str:
    work = tempfile.mkdtemp(prefix="pose_")
    video_path = os.path.join(work, os.path.basename(file.filename or "video.mp4"))
    with open(video_path, "wb") as f:
        f.write(await file.read())
    return video_path

# ---------------------------------------------------------------------------------------------- job
_jobs: "OrderedDict[str, Dict]" = OrderedDict()
_jobs_lock = threading.Lock()
_executor = ThreadPoolExecutor(max_workers=1)  # 1 GPU -> xử lý lần lượt từng video

def _update(job_id: str, **fields) -> None:
    with _jobs_lock:
        if job_id in _jobs:
            _jobs[job_id].update(fields)

def _run_job(job_id: str, video_path: str) -> None:
    _update(job_id, status="PROCESSING", progress="Bắt đầu xử lý")
    try:
        result = process_video(video_path, progress=lambda msg: _update(job_id, progress=msg))
        _update(job_id, status="COMPLETED", progress="Hoàn thành", result=result)
    except Exception as e:
        _update(job_id, status="FAILED", error=str(e))

@app.get("/")
def health():
    return {"status": "online", "backend": POSE_BACKEND, "source": POSE_SOURCE,
            "command": POSE_COMMAND or None, "gvhmr_url": GVHMR_URL if POSE_BACKEND == "gvhmr_api" else None}

@app.post("/jobs", dependencies=[Depends(require_key)])
async def create_job(file: UploadFile = File(...)):
    video_path = await _save_upload(file)
    job_id = uuid.uuid4().hex
    with _jobs_lock:
        _jobs[job_id] = {"job_id": job_id, "status": "PENDING", "progress": "Đang xếp hàng", "result": None, "error": None}
        while len(_jobs) > MAX_JOBS_KEPT:
            _jobs.popitem(last=False)
    _executor.submit(_run_job, job_id, video_path)
    return {"job_id": job_id, "status": "PENDING"}

@app.get("/jobs/{job_id}", dependencies=[Depends(require_key)])
def get_job(job_id: str):
    with _jobs_lock:
        job = _jobs.get(job_id)
        if not job:
            raise HTTPException(404, "Không tìm thấy job")
        return dict(job)

@app.post("/extract", dependencies=[Depends(require_key)])
async def extract(file: UploadFile = File(...)):
    video_path = await _save_upload(file)
    try:
        return await run_in_threadpool(process_video, video_path)
    except PoseServerError as e:
        raise HTTPException(500, str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8100")))
