"""
Dữ liệu cho trình xem khung xương 3D trong báo cáo HTML (FAQ Q8: xoay góc nhìn để xem tư thế sai ở khớp nào).

Với mỗi cặp frame (HLV, HV) trên warping path DTW: khung xương HV được căn Procrustes về khung xương HLV
(đúng phép căn mà điểm PA-MPJPE dùng), cả hai được đưa về tâm, chuẩn hóa theo bán kính cơ thể HLV và
xoay để trục đầu - xương chậu hướng lên trên. Sai số từng khớp (tương đối) dùng để tô đỏ khớp lệch.
"""
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from ..pose_io import H36M_BONES, SMPL_PARENTS, joint_names_for, to_h36m
from ..scorers.pa_mpjpe_dtw_scorer import batched_procrustes_align

MAX_VIEWER_FRAMES = 180   # số cặp frame tối đa nhúng vào báo cáo (giữ file HTML nhỏ)
HEAD_NAME, PELVIS_INDEX = "Đầu", 0

def bones_for(num_joints: int) -> List[Tuple[int, int]]:
    if num_joints == 17:
        return list(H36M_BONES)
    if num_joints in (22, 24):
        return [(SMPL_PARENTS[j], j) for j in range(1, num_joints)]
    return []

def _rotation_to_y(v: np.ndarray) -> np.ndarray:
    """Ma trận quay đưa vector đơn vị v về trục +Y (công thức Rodrigues)."""
    v = v / max(np.linalg.norm(v), 1e-9)
    y = np.array([0.0, 1.0, 0.0])
    axis = np.cross(v, y)
    s, c = np.linalg.norm(axis), float(np.dot(v, y))
    if s < 1e-9:
        return np.eye(3) if c > 0 else np.diag([1.0, -1.0, -1.0])
    k = axis / s
    kx = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + s * kx + (1 - c) * (kx @ kx)

def _up_vector(frames: np.ndarray, names: Sequence[str]) -> np.ndarray:
    """Hướng 'lên' của người tập: từ xương chậu tới đầu (trung bình các frame); không có tên khớp thì dùng PCA."""
    if HEAD_NAME in names:
        head = names.index(HEAD_NAME)
        return (frames[:, head] - frames[:, PELVIS_INDEX]).mean(axis=0)
    pts = (frames - frames.mean(axis=1, keepdims=True)).reshape(-1, 3)
    return np.linalg.svd(pts, full_matrices=False)[2][0]

def build_viewer_data(coach_joints: np.ndarray, student_joints: np.ndarray, warping_path: Sequence[Sequence[int]],
                      tolerance: float, student_frame_times: Optional[Sequence[float]] = None,
                      max_frames: int = MAX_VIEWER_FRAMES) -> Optional[Dict[str, Any]]:
    """
    coach_joints (N, J, 3), student_joints (M, J', 3), warping_path [(frame HLV, frame HV), ...] theo chỉ số pose.
    Trả về dict JSON-hóa được cho trình xem, hoặc None nếu thiếu dữ liệu.
    """
    if coach_joints is None or student_joints is None or not len(warping_path):
        return None
    ref_all = np.asarray(coach_joints, dtype=np.float64)
    stu_all = np.asarray(student_joints, dtype=np.float64)
    if ref_all.ndim != 3 or stu_all.ndim != 3:
        return None
    if ref_all.shape[1] != stu_all.shape[1]:
        ref_h, stu_h = to_h36m(ref_all), to_h36m(stu_all)
        if ref_h is None or stu_h is None:
            return None
        ref_all, stu_all = ref_h, stu_h
    n_joints = ref_all.shape[1]
    names = joint_names_for(n_joints)

    path = [(int(c), int(s)) for c, s in warping_path if 0 <= int(c) < len(ref_all) and 0 <= int(s) < len(stu_all)]
    if not path:
        return None
    if len(path) > max_frames:
        keep = np.unique(np.linspace(0, len(path) - 1, max_frames).round().astype(int))
        path = [path[k] for k in keep]
    ci = np.array([p[0] for p in path])
    si = np.array([p[1] for p in path])
    ref, stu = ref_all[ci], stu_all[si]

    aligned, _ = batched_procrustes_align(ref, stu)
    center = ref.mean(axis=1, keepdims=True)
    radius = np.sqrt(np.mean(np.sum((ref - center) ** 2, axis=-1), axis=1))
    radius = np.where(radius > 1e-9, radius, 1.0)
    rel_err = np.linalg.norm(ref - aligned, axis=-1) / radius[:, None]

    # Chuẩn hóa: tâm về gốc, bán kính cơ thể trung bình = 1, trục đầu - chậu hướng +Y
    rot = _rotation_to_y(_up_vector(ref, names))
    scale = 1.0 / float(np.median(radius))
    ref_n = ((ref - center) * scale) @ rot.T
    stu_n = ((aligned - center) * scale) @ rot.T

    times = list(student_frame_times) if student_frame_times is not None else None
    frames = []
    for k, (c, s) in enumerate(path):
        frames.append({
            "c": np.round(ref_n[k], 3).tolist(),
            "s": np.round(stu_n[k], 3).tolist(),
            "e": np.round(rel_err[k], 3).tolist(),
            "cf": c, "sf": s,
            "t": round(float(times[s]), 2) if times is not None and s < len(times) else None,
        })
    return {"names": names, "bones": bones_for(n_joints), "tolerance": float(tolerance), "frames": frames}
