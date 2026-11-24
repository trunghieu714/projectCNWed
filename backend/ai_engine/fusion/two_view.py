"""
Fusion 2 bộ pose 2D (2 góc quay trái/phải) thành pose 3D - Slide 10.

Tương tự notebook Colab của đề tài: đồng bộ thời gian 2 video, triangulation DLT có trọng số
độ tin cậy, sau đó tinh chỉnh (bài toán tối ưu phi lồi) giữa sai số chiếu lại và ràng buộc
chiều dài xương (chiều dài mỗi xương được giữ ổn định qua các frame).

File hiệu chỉnh camera (AI_CAMERA_CALIB_PATH) dạng JSON:
    {"P1": [[...4 số...] x 3], "P2": [[...] x 3]}
hoặc {"cameras": [{"K": 3x3, "R": 3x3, "t": [3]}, {...}]}
"""
import json
from typing import Dict, Optional, Tuple

import numpy as np

from ..pose_io import H36M_BONES

def load_projection_matrices(path: str) -> Tuple[np.ndarray, np.ndarray]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if "P1" in data and "P2" in data:
        return np.asarray(data["P1"], dtype=np.float64), np.asarray(data["P2"], dtype=np.float64)
    cams = data.get("cameras", [])
    if len(cams) < 2:
        raise ValueError("File hiệu chỉnh cần 2 camera")
    mats = []
    for cam in cams[:2]:
        k = np.asarray(cam["K"], dtype=np.float64)
        r = np.asarray(cam["R"], dtype=np.float64)
        t = np.asarray(cam["t"], dtype=np.float64).reshape(3, 1)
        mats.append(k @ np.hstack([r, t]))
    return mats[0], mats[1]

def estimate_time_offset(kp_a: np.ndarray, kp_b: np.ndarray, max_shift: int = 30) -> int:
    """
    Độ lệch frame giữa 2 video (b trễ hơn a `delta` frame) bằng tương quan chéo của
    năng lượng chuyển động - FAQ Q4: 2 video quay cùng lúc nhưng có thể lệch vài frame.
    """
    def energy(kp):
        v = np.linalg.norm(np.diff(kp, axis=0), axis=-1).mean(axis=1)
        return (v - v.mean()) / (v.std() + 1e-9)
    ea, eb = energy(kp_a), energy(kp_b)
    best, best_score = 0, -np.inf
    for d in range(-max_shift, max_shift + 1):
        # Ghép a[t] với b[t + d]
        if d >= 0:
            a, b = ea, eb[d:]
        else:
            a, b = ea[-d:], eb
        length = min(len(a), len(b))
        if length < 10:
            continue
        score = float(np.dot(a[:length], b[:length]) / length)
        if score > best_score:
            best, best_score = d, score
    return best

def triangulate_dlt(p1: np.ndarray, p2: np.ndarray, x1: np.ndarray, x2: np.ndarray,
                    w1: Optional[np.ndarray] = None, w2: Optional[np.ndarray] = None) -> np.ndarray:
    """x1, x2: (J, 2) -> (J, 3). Trọng số w là độ tin cậy của YOLO cho từng khớp."""
    j = x1.shape[0]
    w1 = np.ones(j) if w1 is None else w1
    w2 = np.ones(j) if w2 is None else w2
    out = np.zeros((j, 3))
    for k in range(j):
        a = np.stack([
            w1[k] * (x1[k, 0] * p1[2] - p1[0]),
            w1[k] * (x1[k, 1] * p1[2] - p1[1]),
            w2[k] * (x2[k, 0] * p2[2] - p2[0]),
            w2[k] * (x2[k, 1] * p2[2] - p2[1]),
        ])
        _, _, vt = np.linalg.svd(a)
        xh = vt[-1]
        out[k] = xh[:3] / (xh[3] if abs(xh[3]) > 1e-12 else 1e-12)
    return out

def _project(p: np.ndarray, pts: np.ndarray) -> np.ndarray:
    h = np.hstack([pts, np.ones((len(pts), 1))]) @ p.T
    return h[:, :2] / h[:, 2:3]

def refine_with_bone_lengths(p1, p2, x1, x2, init: np.ndarray, bone_lengths: np.ndarray, bone_weight: float = 1.0) -> np.ndarray:
    """Tối ưu phi lồi: sai số chiếu lại 2 camera + độ lệch so với chiều dài xương chuẩn."""
    try:
        from scipy.optimize import least_squares
    except ImportError:
        return init
    bones = np.array(H36M_BONES)
    scale = max(float(np.median(bone_lengths)), 1e-6)

    def residual(flat):
        pts = flat.reshape(-1, 3)
        r1 = (_project(p1, pts) - x1).ravel()
        r2 = (_project(p2, pts) - x2).ravel()
        lengths = np.linalg.norm(pts[bones[:, 0]] - pts[bones[:, 1]], axis=-1)
        rb = bone_weight * (lengths - bone_lengths) / scale * 10.0
        return np.concatenate([r1, r2, rb])

    res = least_squares(residual, init.ravel(), method="lm" if init.size <= 60 else "trf", max_nfev=200)
    return res.x.reshape(-1, 3)

def fuse_two_views(left: Dict, right: Dict, p1: np.ndarray, p2: np.ndarray, bone_weight: float = 1.0) -> Dict:
    """
    left/right: kết quả YoloPoseEstimator (có keypoints_2d (N,17,2) toạ độ pixel và keypoints_conf).
    Trả về {"joints_3d": (N,17,3), "time_offset": delta}.
    """
    ka, kb = np.asarray(left["keypoints_2d"]), np.asarray(right["keypoints_2d"])
    ca = np.asarray(left.get("keypoints_conf", np.ones(ka.shape[:2])))
    cb = np.asarray(right.get("keypoints_conf", np.ones(kb.shape[:2])))
    delta = estimate_time_offset(ka, kb, max_shift=min(30, len(ka) // 4, len(kb) // 4) or 1)
    ia = np.arange(len(ka))
    ib = ia + delta
    keep = (ib >= 0) & (ib < len(kb))
    ia, ib = ia[keep], ib[keep]
    init = np.stack([triangulate_dlt(p1, p2, ka[i], kb[j], ca[i], cb[j]) for i, j in zip(ia, ib)])
    bones = np.array(H36M_BONES)
    bone_lengths = np.median(np.linalg.norm(init[:, bones[:, 0]] - init[:, bones[:, 1]], axis=-1), axis=0)
    refined = np.stack([
        refine_with_bone_lengths(p1, p2, ka[i], kb[j], init[k], bone_lengths, bone_weight)
        for k, (i, j) in enumerate(zip(ia, ib))
    ])
    frame_indices = [left["frame_indices"][i] for i in ia]
    return {"joints_3d": refined, "time_offset": int(delta), "frame_indices": frame_indices}
