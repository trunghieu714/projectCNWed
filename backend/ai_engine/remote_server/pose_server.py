"""
Server trích xuất pose 3D chạy trên Google Colab / PC có GPU (FAQ Q5: được host pipeline AI lên Colab).

Server nhận video, chạy lệnh của mô hình monocular (WHAM / GVHMR / TCPFormer...) rồi đọc file kết quả
bằng ai_engine.pose_io (hỗ trợ .pkl / .pt / .npz / .npy / .json) và trả JSON khớp 3D cho backend
(estimator "remote", biến môi trường AI_REMOTE_URL).

Chạy trên Colab (sau khi đã cài WHAM hoặc GVHMR theo README của repo tương ứng):

    !pip install fastapi uvicorn python-multipart pyngrok
    %cd /content/GVHMR
    import os
    os.environ["POSE_COMMAND"] = "python tools/demo/demo.py --video={video} --output_root={out_dir} -s"
    # WHAM: "python demo.py --video {video} --output_pth {out_dir} --save_pkl"
    !PYTHONPATH=/content/projectCNWed/backend python -m ai_engine.remote_server.pose_server &
    from pyngrok import ngrok; print(ngrok.connect(8100))   # dán URL này vào AI_REMOTE_URL

Nếu không đặt POSE_COMMAND, server dùng YOLO pose (ultralytics) làm phương án dự phòng.
"""
import glob
import os
import shlex
import subprocess
import tempfile
import time

import uvicorn
from fastapi import FastAPI, File, HTTPException, UploadFile

from ai_engine.pose_io import PoseNotAvailable, load_pose_file, read_video_meta

POSE_COMMAND = os.environ.get("POSE_COMMAND", "").strip()
POSE_SOURCE = os.environ.get("POSE_SOURCE", "gvhmr" if "gvhmr" in POSE_COMMAND.lower() else "wham" if POSE_COMMAND else "yolo")
TIMEOUT = int(os.environ.get("POSE_TIMEOUT", "1200"))
RESULT_PATTERNS = ("**/*.pkl", "**/*.pt", "**/*.npz", "**/*.npy", "**/*.json")

app = FastAPI(title="Pose 3D Extraction Server")

@app.get("/")
def health():
    return {"status": "online", "source": POSE_SOURCE, "command": POSE_COMMAND or "builtin-yolo"}

def _run_model(video_path: str, out_dir: str):
    cmd = POSE_COMMAND.format(video=shlex.quote(video_path), out_dir=shlex.quote(out_dir))
    res = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=TIMEOUT)
    if res.returncode != 0:
        raise HTTPException(500, f"Lệnh mô hình lỗi: {res.stderr.decode('utf-8', 'ignore')[-1500:]}")
    started = os.path.getmtime(video_path)
    files = []
    for pattern in RESULT_PATTERNS:
        files += [f for f in glob.glob(os.path.join(out_dir, pattern), recursive=True) if os.path.getmtime(f) >= started - 1]
    for f in sorted(files, key=os.path.getmtime, reverse=True):
        try:
            return load_pose_file(f), os.path.basename(f)
        except PoseNotAvailable:
            continue
    raise HTTPException(500, "Mô hình chạy xong nhưng không tìm thấy file pose 3D trong thư mục kết quả.")

@app.post("/extract")
async def extract(file: UploadFile = File(...)):
    work = tempfile.mkdtemp(prefix="pose_")
    video_path = os.path.join(work, os.path.basename(file.filename or "video.mp4"))
    with open(video_path, "wb") as f:
        f.write(await file.read())
    t0 = time.time()
    fps, _ = read_video_meta(video_path)
    if POSE_COMMAND:
        joints, result_file = _run_model(video_path, os.path.join(work, "out"))
        frame_indices = list(range(len(joints)))
    else:
        from ai_engine.models.yolo_estimator import YoloPoseEstimator
        try:
            pose = YoloPoseEstimator(weights=os.environ.get("YOLO_POSE_WEIGHTS", "yolo26x-pose.pt")).extract_poses(video_path)
        except PoseNotAvailable as e:
            raise HTTPException(500, str(e))
        joints, fps, frame_indices, result_file = pose["joints_3d"], pose["fps"], pose["frame_indices"], "yolo"
    return {
        "joints_3d": joints.round(5).tolist(),
        "fps": fps,
        "frame_indices": frame_indices,
        "source": f"{POSE_SOURCE}:{result_file}",
        "seconds": round(time.time() - t0, 1),
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8100")))
