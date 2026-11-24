"""
Tiện ích đọc / chuẩn hóa dữ liệu pose dùng chung cho toàn bộ AI engine.

- Đọc kết quả của các mô hình monocular (WHAM, GVHMR, TCPFormer...) lưu dưới dạng
  .pkl / .pt / .npy / .npz / .json và đưa về một mảng khớp 3D duy nhất (N_frames, J, 3).
- Hỗ trợ tham số SMPL dạng axis-angle (WHAM lưu 'pose'/'pose_world' (N,72),
  GVHMR lưu 'global_orient' + 'body_pose') bằng forward kinematics trên bộ xương SMPL chuẩn.
- Chuyển COCO-17 (YOLO) sang Human3.6M-17.
- Bộ nhớ đệm pose (pose của video HLV được trích xuất một lần, dùng lại cho mọi bài nộp).
"""
import hashlib
import json
import os
import pickle
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

H36M_JOINT_NAMES = [
    "Xương chậu", "Hông phải", "Gối phải", "Cổ chân phải", "Hông trái", "Gối trái", "Cổ chân trái",
    "Cột sống", "Ngực", "Cổ", "Đầu", "Vai trái", "Khuỷu tay trái", "Cổ tay trái",
    "Vai phải", "Khuỷu tay phải", "Cổ tay phải",
]
H36M_BONES = [(0, 1), (1, 2), (2, 3), (0, 4), (4, 5), (5, 6), (0, 7), (7, 8), (8, 9), (9, 10),
              (8, 11), (11, 12), (12, 13), (8, 14), (14, 15), (15, 16)]

SMPL_JOINT_NAMES = [
    "Xương chậu", "Hông trái", "Hông phải", "Cột sống 1", "Gối trái", "Gối phải", "Cột sống 2",
    "Cổ chân trái", "Cổ chân phải", "Cột sống 3", "Bàn chân trái", "Bàn chân phải", "Cổ",
    "Xương đòn trái", "Xương đòn phải", "Đầu", "Vai trái", "Vai phải", "Khuỷu tay trái",
    "Khuỷu tay phải", "Cổ tay trái", "Cổ tay phải", "Bàn tay trái", "Bàn tay phải",
]
SMPL_PARENTS = [-1, 0, 0, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 9, 9, 12, 13, 14, 16, 17, 18, 19, 20, 21]
# Độ lệch khớp con so với khớp cha của bộ xương SMPL trung tính ở tư thế T (mét, xấp xỉ).
# Dùng chung một bộ xương cho cả HLV và HV nên so sánh chỉ phản ánh tư thế, không phụ thuộc vóc dáng.
SMPL_REST_OFFSETS = np.array([
    [0.000, 0.000, 0.000], [0.058, -0.082, -0.018], [-0.060, -0.091, -0.014], [0.004, 0.124, -0.038],
    [0.043, -0.386, 0.008], [-0.043, -0.383, -0.005], [0.004, 0.138, 0.027], [-0.015, -0.427, -0.037],
    [0.019, -0.420, -0.035], [-0.002, 0.056, 0.002], [0.041, -0.060, 0.122], [-0.035, -0.062, 0.130],
    [-0.013, 0.212, -0.033], [0.072, 0.114, -0.019], [-0.083, 0.112, -0.024], [0.010, 0.089, 0.050],
    [0.123, 0.045, -0.019], [-0.113, 0.047, -0.008], [0.255, -0.016, -0.023], [-0.260, -0.014, -0.031],
    [0.266, 0.009, -0.006], [-0.269, -0.007, -0.006], [0.087, -0.011, -0.016], [-0.089, -0.009, -0.010],
], dtype=np.float64)
# SMPL-24 -> H36M-17 (cùng thứ tự với H36M_JOINT_NAMES)
SMPL_TO_H36M = [0, 2, 5, 8, 1, 4, 7, 6, 12, 12, 15, 16, 18, 20, 17, 19, 21]
# COCO-17 (YOLO pose) -> H36M-17, khớp ảo lấy trung bình nhiều khớp (giống notebook Colab slide 10)
COCO_TO_H36M = {
    0: [11, 12], 1: [12], 2: [14], 3: [16], 4: [11], 5: [13], 6: [15],
    7: [5, 6, 11, 12], 8: [5, 6], 9: [0], 10: [0], 11: [5], 12: [7],
    13: [9], 14: [6], 15: [8], 16: [10],
}

_JOINT_HINTS = ("joint", "kp3d", "j3d", "keypoints_3d", "pose3d", "pose_3d", "joints3d", "skeleton")

class PoseNotAvailable(Exception):
    """Estimator không thể cung cấp pose cho video này (thiếu file, thiếu thư viện, server lỗi...)."""

def joint_names_for(num_joints: int) -> List[str]:
    if num_joints == 17:
        return list(H36M_JOINT_NAMES)
    if num_joints in (22, 24):
        return SMPL_JOINT_NAMES[:num_joints]
    return [f"Khớp {i}" for i in range(num_joints)]

# ----------------------------------------------------------------------------------------------
# Forward kinematics SMPL
# ----------------------------------------------------------------------------------------------
def axis_angle_to_matrix(vecs: np.ndarray) -> np.ndarray:
    """(..., 3) axis-angle -> (..., 3, 3) ma trận quay (công thức Rodrigues, vector hóa)."""
    vecs = np.asarray(vecs, dtype=np.float64)
    theta = np.linalg.norm(vecs, axis=-1, keepdims=True)
    axis = vecs / np.maximum(theta, 1e-8)
    x, y, z = axis[..., 0], axis[..., 1], axis[..., 2]
    zeros = np.zeros_like(x)
    k = np.stack([zeros, -z, y, z, zeros, -x, -y, x, zeros], axis=-1).reshape(vecs.shape[:-1] + (3, 3))
    eye = np.broadcast_to(np.eye(3), k.shape)
    s = np.sin(theta)[..., None]
    c = np.cos(theta)[..., None]
    return eye + s * k + (1 - c) * (k @ k)

def smpl_forward_kinematics(axis_angles: np.ndarray, transl: Optional[np.ndarray] = None) -> np.ndarray:
    """axis_angles (N, 24, 3) hoặc (N, 72) -> vị trí 24 khớp (N, 24, 3)."""
    aa = np.asarray(axis_angles, dtype=np.float64)
    n = aa.shape[0]
    aa = aa.reshape(n, -1, 3)
    if aa.shape[1] < 24:
        aa = np.concatenate([aa, np.zeros((n, 24 - aa.shape[1], 3))], axis=1)
    aa = aa[:, :24]
    rots = axis_angle_to_matrix(aa)
    glob_rot = np.zeros((n, 24, 3, 3))
    pos = np.zeros((n, 24, 3))
    for j in range(24):
        parent = SMPL_PARENTS[j]
        if parent < 0:
            glob_rot[:, j] = rots[:, j]
            pos[:, j] = 0.0
        else:
            glob_rot[:, j] = glob_rot[:, parent] @ rots[:, j]
            pos[:, j] = pos[:, parent] + np.einsum("nij,j->ni", glob_rot[:, parent], SMPL_REST_OFFSETS[j])
    if transl is not None:
        t = np.asarray(transl, dtype=np.float64).reshape(n, 1, 3)
        pos = pos + t
    return pos

# ----------------------------------------------------------------------------------------------
# Đọc file pose bất kỳ
# ----------------------------------------------------------------------------------------------
def _to_numpy(x: Any) -> Optional[np.ndarray]:
    if hasattr(x, "detach") and hasattr(x, "cpu"):  # torch.Tensor
        try:
            return x.detach().cpu().numpy()
        except Exception:
            return None
    if isinstance(x, np.ndarray):
        return x if np.issubdtype(x.dtype, np.number) else None
    if isinstance(x, (list, tuple)) and x and all(isinstance(v, (int, float)) for v in np.ravel(np.asarray(x, dtype=object))[:50]):
        try:
            arr = np.asarray(x, dtype=np.float64)
            return arr
        except Exception:
            return None
    return None

def _collect_arrays(obj: Any, path: str = "root", depth: int = 0, out: Optional[List[Tuple[str, np.ndarray]]] = None):
    if out is None:
        out = []
    if depth > 6:
        return out
    arr = _to_numpy(obj)
    if arr is not None:
        out.append((path, arr))
        return out
    if isinstance(obj, dict):
        for k, v in obj.items():
            _collect_arrays(v, f"{path}.{k}", depth + 1, out)
    elif isinstance(obj, (list, tuple)):
        # Danh sách các frame dạng dict -> gộp theo key
        if obj and all(isinstance(v, dict) for v in obj[:5]):
            keys = set(obj[0].keys())
            for key in keys:
                vals = [_to_numpy(v.get(key)) for v in obj]
                if all(v is not None for v in vals) and len({v.shape for v in vals}) == 1:
                    out.append((f"{path}[].{key}", np.stack(vals)))
        for i, v in enumerate(obj[:8]):
            _collect_arrays(v, f"{path}[{i}]", depth + 1, out)
    elif hasattr(obj, "__dict__") and not isinstance(obj, type):
        _collect_arrays(vars(obj), path, depth + 1, out)
    return out

def _pick_joints(arrays: List[Tuple[str, np.ndarray]]) -> Optional[np.ndarray]:
    best, best_rank = None, -1
    for name, arr in arrays:
        a = np.squeeze(arr)
        if a.ndim == 4 and a.shape[-1] == 3:  # (persons, N, J, 3) -> người đầu tiên
            a = a[0]
        if a.ndim != 3 or a.shape[-1] != 3 or a.shape[0] < 2 or not (14 <= a.shape[1] <= 130):
            continue
        if not np.isfinite(a).all():
            continue
        lname = name.lower()
        rank = 1
        if any(h in lname for h in _JOINT_HINTS):
            rank += 5
        if "world" in lname:
            rank += 1
        if any(h in lname for h in ("vert", "mesh", "2d", "uv")):
            rank -= 4
        if a.shape[1] in (17, 22, 24):
            rank += 2
        if rank > best_rank:
            best, best_rank = a, rank
    return best

def _find_named(arrays: List[Tuple[str, np.ndarray]], key: str, last_dim: int) -> Optional[np.ndarray]:
    for name, arr in arrays:
        if name.lower().endswith(key) and arr.ndim >= 2 and arr.shape[-1] == last_dim:
            return arr.reshape(arr.shape[0], -1) if arr.ndim > 2 else arr
    return None

def _pick_smpl_pose(arrays: List[Tuple[str, np.ndarray]]) -> Optional[np.ndarray]:
    """Tìm tham số SMPL axis-angle (WHAM: pose_world/pose (N,72); GVHMR: global_orient + body_pose)."""
    for key in ("pose_world", "poses", "pose", "smpl_pose", "full_pose"):
        for name, arr in arrays:
            a = np.squeeze(arr)
            if name.lower().endswith("." + key) and a.ndim == 2 and a.shape[1] in (66, 72) and a.shape[0] >= 2:
                return a
    go = _find_named(arrays, "global_orient", 3)
    bp = None
    for name, arr in arrays:
        a = arr.reshape(arr.shape[0], -1) if arr.ndim >= 2 else arr
        if name.lower().endswith("body_pose") and a.ndim == 2 and a.shape[1] in (63, 69):
            bp = a
            break
    if go is not None and bp is not None and go.shape[0] == bp.shape[0]:
        return np.concatenate([go, bp], axis=1)
    return None

def _pose_from_time_series(obj: Any) -> Optional[np.ndarray]:
    """Định dạng time_series_poses của đặc tả get_post: [{frame_id, poses:[{pose_name, pose_coord:{x,y,z}}]}]."""
    frames = obj.get("time_series_poses") if isinstance(obj, dict) else obj
    if not isinstance(frames, list) or not frames or not isinstance(frames[0], dict) or "poses" not in frames[0]:
        return None
    seq = []
    for fr in frames:
        pts = []
        for p in fr.get("poses", []):
            c = p.get("pose_coord", {})
            if isinstance(c, dict):
                pts.append([float(c.get("x", 0)), float(c.get("y", 0)), float(c.get("z", 0))])
            else:
                pts.append([float(v) for v in list(c)[:3]])
        seq.append(pts)
    arr = np.asarray(seq, dtype=np.float64)
    return arr if arr.ndim == 3 and arr.shape[-1] == 3 else None

def load_raw(path: str) -> Any:
    ext = os.path.splitext(path)[1].lower()
    if ext in (".pkl", ".pickle"):
        try:
            with open(path, "rb") as f:
                return pickle.load(f)
        except Exception:
            import joblib  # WHAM lưu bằng joblib.dump
            return joblib.load(path)
    if ext == ".npy":
        return np.load(path, allow_pickle=True)
    if ext == ".npz":
        data = np.load(path, allow_pickle=True)
        return {k: data[k] for k in data.files}
    if ext == ".json":
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    if ext in (".pt", ".pth"):
        import torch  # GVHMR: hmr4d_results.pt
        return torch.load(path, map_location="cpu", weights_only=False)
    raise PoseNotAvailable(f"Không hỗ trợ định dạng pose {ext}")

def _gvhmr_joints(obj: Any) -> Optional[np.ndarray]:
    """hmr4d_results.pt của GVHMR: ưu tiên smpl_params_global (hệ trọng lực), sau đó smpl_params_incam."""
    if not isinstance(obj, dict):
        return None
    for key in ("smpl_params_global", "smpl_params_incam"):
        params = obj.get(key)
        if not isinstance(params, dict):
            continue
        go, bp = _to_numpy(params.get("global_orient")), _to_numpy(params.get("body_pose"))
        if go is None or bp is None or go.shape[0] != bp.shape[0] or go.shape[0] < 2:
            continue
        n = go.shape[0]
        return smpl_forward_kinematics(np.concatenate([go.reshape(n, -1), bp.reshape(n, -1)], axis=1))
    return None

def extract_joints(obj: Any) -> np.ndarray:
    """Từ một object bất kỳ (kết quả WHAM/GVHMR/TCPFormer/JSON) -> mảng khớp 3D (N, J, 3)."""
    if isinstance(obj, np.ndarray) and obj.dtype == object and obj.shape == ():
        obj = obj.item()
    gvhmr = _gvhmr_joints(obj)
    if gvhmr is not None:
        return gvhmr
    # WHAM: {subject_id: {...}} -> chọn người xuất hiện nhiều frame nhất
    if isinstance(obj, dict) and obj and all(isinstance(k, (int, np.integer)) for k in obj.keys()):
        obj = max(obj.values(), key=lambda v: len(v.get("frame_ids", [])) if isinstance(v, dict) else 0)
    ts = _pose_from_time_series(obj)
    if ts is not None:
        return ts
    arrays = _collect_arrays(obj)
    joints = _pick_joints(arrays)
    if joints is not None:
        return joints.astype(np.float64)
    smpl = _pick_smpl_pose(arrays)
    if smpl is not None:
        return smpl_forward_kinematics(smpl)
    raise PoseNotAvailable("Không tìm thấy dữ liệu khớp 3D hoặc tham số SMPL trong file pose.")

def load_pose_file(path: str) -> np.ndarray:
    return extract_joints(load_raw(path))

# ----------------------------------------------------------------------------------------------
# Chuẩn hóa & đặc trưng
# ----------------------------------------------------------------------------------------------
def coco_to_h36m(kps: np.ndarray) -> np.ndarray:
    """(N, 17, D) COCO -> (N, 17, D) H36M."""
    kps = np.asarray(kps, dtype=np.float64)
    out = np.zeros_like(kps)
    for h_idx, c_idxs in COCO_TO_H36M.items():
        out[:, h_idx] = kps[:, c_idxs].mean(axis=1)
    return out

def to_h36m(joints: np.ndarray) -> Optional[np.ndarray]:
    j = joints.shape[1]
    if j == 17:
        return joints
    if j in (22, 24) or j > 24:
        idx = [min(i, j - 1) for i in SMPL_TO_H36M]
        return joints[:, idx]
    return None

def _angle(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> np.ndarray:
    v1, v2 = a - b, c - b
    cos = np.sum(v1 * v2, axis=-1) / np.maximum(np.linalg.norm(v1, axis=-1) * np.linalg.norm(v2, axis=-1), 1e-8)
    return np.degrees(np.arccos(np.clip(cos, -1.0, 1.0)))

def joint_angles_from_joints(joints: np.ndarray) -> np.ndarray:
    """5 góc khớp chính (khuỷu T/P, gối T/P, độ gập thân) - giữ tương thích với FastDTWScorer."""
    h = to_h36m(joints)
    if h is None:
        return np.zeros((joints.shape[0], 5))
    up = h[:, 10] - h[:, 0]
    vertical = np.zeros_like(up)
    vertical[:, 1] = 1.0
    trunk = np.degrees(np.arccos(np.clip(np.abs(np.sum(up * vertical, -1)) / np.maximum(np.linalg.norm(up, axis=-1), 1e-8), -1, 1)))
    return np.stack([
        _angle(h[:, 11], h[:, 12], h[:, 13]),
        _angle(h[:, 14], h[:, 15], h[:, 16]),
        _angle(h[:, 4], h[:, 5], h[:, 6]),
        _angle(h[:, 1], h[:, 2], h[:, 3]),
        trunk,
    ], axis=1)

def build_pose_result(joints: np.ndarray, fps: float, source: str, frame_indices: Optional[List[int]] = None,
                      keypoints_2d: Optional[np.ndarray] = None, dims: int = 3) -> Dict[str, Any]:
    joints = np.asarray(joints, dtype=np.float64)
    n = joints.shape[0]
    return {
        "joints_3d": joints,
        "keypoints_3d": joints,
        "keypoints_2d": keypoints_2d,
        "joint_names": joint_names_for(joints.shape[1]),
        "joint_angles": joint_angles_from_joints(joints),
        "fps": float(fps),
        "total_frames": n,
        "frame_indices": list(frame_indices) if frame_indices is not None else list(range(n)),
        "source": source,
        "dims": dims,
    }

def read_video_meta(video_path: str) -> Tuple[float, int]:
    """(fps, số frame) của video; (30, 0) nếu không đọc được."""
    try:
        import cv2
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return 30.0, 0
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        cap.release()
        return float(fps if fps > 0 else 30.0), max(n, 0)
    except Exception:
        return 30.0, 0

# ----------------------------------------------------------------------------------------------
# Bộ nhớ đệm pose
# ----------------------------------------------------------------------------------------------
class PoseCache:
    """Lưu kết quả trích xuất pose ra file .npz để không phải chạy lại mô hình cho video HLV."""

    def __init__(self, cache_dir: str = "storage/pose_cache"):
        self.cache_dir = cache_dir

    def key(self, video_path: str, estimator_name: str) -> str:
        try:
            st = os.stat(video_path)
            sig = f"{os.path.abspath(video_path)}|{st.st_size}|{int(st.st_mtime)}|{estimator_name}"
        except OSError:
            sig = f"{video_path}|{estimator_name}"
        return hashlib.sha1(sig.encode("utf-8")).hexdigest()

    def path_for(self, video_path: str, estimator_name: str) -> str:
        return os.path.join(self.cache_dir, self.key(video_path, estimator_name) + ".npz")

    def load(self, video_path: str, estimator_name: str) -> Optional[Dict[str, Any]]:
        p = self.path_for(video_path, estimator_name)
        if not os.path.exists(p):
            return None
        try:
            data = np.load(p, allow_pickle=False)
            kp2d = data["keypoints_2d"] if "keypoints_2d" in data.files else None
            return build_pose_result(
                data["joints_3d"], float(data["fps"]), str(data["source"]) + " (cache)",
                frame_indices=data["frame_indices"].tolist(), keypoints_2d=kp2d, dims=int(data["dims"]),
            )
        except Exception:
            return None

    def save(self, video_path: str, estimator_name: str, pose: Dict[str, Any]) -> str:
        os.makedirs(self.cache_dir, exist_ok=True)
        p = self.path_for(video_path, estimator_name)
        extra = {}
        if pose.get("keypoints_2d") is not None:
            extra["keypoints_2d"] = np.asarray(pose["keypoints_2d"])
        np.savez_compressed(
            p, joints_3d=np.asarray(pose["joints_3d"]), fps=pose.get("fps", 30.0),
            frame_indices=np.asarray(pose.get("frame_indices", [])), source=pose.get("source", ""),
            dims=pose.get("dims", 3), **extra,
        )
        return p
