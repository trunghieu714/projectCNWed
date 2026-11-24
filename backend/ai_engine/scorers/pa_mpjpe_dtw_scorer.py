"""
Chấm điểm động tác bằng DTW trên khoảng cách PA-MPJPE giữa các frame khớp 3D.

Bám theo code mẫu của giảng viên (FAQ Q8 - dtw_pkl_grader_html_report_final.py):
- DTW chỉ căn chỉnh theo thời gian, trả về các cặp (frame HLV, frame HV).
- Khoảng cách mỗi cặp frame là PA-MPJPE (căn chỉnh Procrustes: tịnh tiến + quay + tỉ lệ)
  nên không phụ thuộc vị trí đứng, hướng camera hay vóc dáng người tập.
- Cửa sổ Sakoe-Chiba quanh đường chéo để tránh căn chỉnh bất thường.
"""
from collections import Counter
from typing import Any, Dict, List, Tuple

import numpy as np

from ..base.scorer import BaseScorer
from ..pose_io import joint_names_for, to_h36m

MAX_SCORING_FRAMES = 400

def batched_pa_joint_errors(ref: np.ndarray, stu: np.ndarray) -> np.ndarray:
    """ref, stu: (K, J, 3) -> sai số từng khớp sau căn chỉnh Procrustes (K, J)."""
    mu_r = ref.mean(axis=1, keepdims=True)
    mu_s = stu.mean(axis=1, keepdims=True)
    x = ref - mu_r
    y = stu - mu_s
    nx = np.sqrt(np.sum(x * x, axis=(1, 2), keepdims=True))
    ny = np.sqrt(np.sum(y * y, axis=(1, 2), keepdims=True))
    valid = (nx[:, 0, 0] > 1e-9) & (ny[:, 0, 0] > 1e-9)
    nx_s = np.where(nx > 1e-9, nx, 1.0)
    ny_s = np.where(ny > 1e-9, ny, 1.0)
    xn, yn = x / nx_s, y / ny_s
    h = np.einsum("kji,kjl->kil", yn, xn)
    u, s, vt = np.linalg.svd(h)
    det = np.linalg.det(u @ vt)
    flip = det < 0
    vt[flip, -1, :] *= -1
    s[flip, -1] *= -1
    r = u @ vt
    scale = s.sum(axis=1)[:, None, None]
    aligned = scale * np.einsum("kji,kil->kjl", yn, r) * nx_s + mu_r
    err = np.linalg.norm(ref - aligned, axis=-1)
    # Frame suy biến (mọi khớp trùng nhau) -> so sánh trực tiếp sau khi trừ tâm
    if not valid.all():
        err[~valid] = np.linalg.norm(x[~valid] - y[~valid], axis=-1)
    return err

def _subsample(seq: np.ndarray, max_len: int) -> Tuple[np.ndarray, np.ndarray]:
    if len(seq) <= max_len:
        return seq, np.arange(len(seq))
    idx = np.unique(np.linspace(0, len(seq) - 1, max_len).round().astype(int))
    return seq[idx], idx

class PAMPJPEDTWScorer(BaseScorer):
    def __init__(self, window_ratio: float = 0.1, tolerance: float = 0.12, max_error: float = 0.45):
        """
        window_ratio: bán kính cửa sổ Sakoe-Chiba theo tỉ lệ độ dài chuỗi (0 = DTW đầy đủ).
        tolerance:    sai số tương đối (PA-MPJPE / bán kính cơ thể) vượt ngưỡng này bị tính là lỗi.
        max_error:    sai số tương đối trung bình ứng với 0 điểm (0 sai số = 100 điểm).
        """
        super().__init__(name="PA-MPJPE-DTW")
        self.window_ratio = window_ratio
        self.tolerance = tolerance
        self.max_error = max_error

    # ------------------------------------------------------------------------------------------
    def _band(self, n: int, m: int) -> List[Tuple[int, int]]:
        radius = 0 if self.window_ratio <= 0 else max(8, int(round(max(n, m) * self.window_ratio)))
        pairs = []
        for i in range(n):
            if radius == 0:
                lo, hi = 0, m - 1
            else:
                center = int(round(i * (m - 1) / max(n - 1, 1)))
                lo, hi = max(0, center - radius), min(m - 1, center + radius)
            pairs.extend((i, j) for j in range(lo, hi + 1))
        return pairs

    @staticmethod
    def _dtw(dist: np.ndarray) -> List[Tuple[int, int]]:
        n, m = dist.shape
        cost = np.full((n + 1, m + 1), np.inf)
        cost[0, 0] = 0.0
        for i in range(1, n + 1):
            row = dist[i - 1]
            cols = np.nonzero(np.isfinite(row))[0]
            for j0 in cols:
                j = j0 + 1
                best = min(cost[i - 1, j], cost[i, j - 1], cost[i - 1, j - 1])
                if np.isfinite(best):
                    cost[i, j] = row[j0] + best
        i, j = n, m
        path = [(i - 1, j - 1)]
        while i > 1 or j > 1:
            options = [(cost[i - 1, j - 1], i - 1, j - 1), (cost[i - 1, j], i - 1, j), (cost[i, j - 1], i, j - 1)]
            _, i, j = min(options, key=lambda o: o[0])
            if i < 1 or j < 1:
                break
            path.append((i - 1, j - 1))
        path.reverse()
        return path

    @staticmethod
    def _unit_factor(ref: np.ndarray) -> Tuple[float, str]:
        radius = float(np.median(np.sqrt(np.mean(np.sum((ref - ref.mean(axis=1, keepdims=True)) ** 2, axis=-1), axis=1))))
        if 0.05 < radius < 3.0:
            return 1000.0, "mm"   # dữ liệu tính bằng mét (WHAM/GVHMR/SMPL)
        if radius >= 30.0:
            return 1.0, "mm"
        return 0.0, ""

    # ------------------------------------------------------------------------------------------
    def evaluate(self, coach_data: Dict[str, Any], student_data: Dict[str, Any]) -> Dict[str, Any]:
        ref_full = coach_data.get("joints_3d")
        stu_full = student_data.get("joints_3d")
        if ref_full is None or stu_full is None or len(ref_full) == 0 or len(stu_full) == 0:
            return {
                "final_score": 0.0, "warping_path": [], "frame_errors": [], "segments": [],
                "feedback_summary": "Lỗi: Không phát hiện được dữ liệu khung xương hợp lệ từ video.",
            }
        ref_full = np.asarray(ref_full, dtype=np.float64)
        stu_full = np.asarray(stu_full, dtype=np.float64)
        names = coach_data.get("joint_names")
        if ref_full.shape[1] != stu_full.shape[1]:
            # Hai nguồn pose khác bộ xương (vd SMPL-24 và H36M-17) -> đưa cả hai về H36M-17
            ref_h, stu_h = to_h36m(ref_full), to_h36m(stu_full)
            if ref_h is not None and stu_h is not None:
                ref_full, stu_full, names = ref_h, stu_h, None
        n_joints = min(ref_full.shape[1], stu_full.shape[1])
        ref_full, stu_full = ref_full[:, :n_joints], stu_full[:, :n_joints]
        names = list(names or joint_names_for(n_joints))[:n_joints]

        ref, ref_idx = _subsample(ref_full, MAX_SCORING_FRAMES)
        stu, stu_idx = _subsample(stu_full, MAX_SCORING_FRAMES)
        n, m = len(ref), len(stu)

        pairs = self._band(n, m)
        pi = np.array([p[0] for p in pairs])
        pj = np.array([p[1] for p in pairs])
        joint_err = batched_pa_joint_errors(ref[pi], stu[pj])
        body_radius = np.sqrt(np.mean(np.sum((ref - ref.mean(axis=1, keepdims=True)) ** 2, axis=-1), axis=1))
        body_radius = np.where(body_radius > 1e-9, body_radius, 1.0)
        rel = joint_err.mean(axis=1) / body_radius[pi]

        dist = np.full((n, m), np.inf)
        dist[pi, pj] = rel
        pair_lookup = {p: k for k, p in enumerate(pairs)}
        path = self._dtw(dist)

        unit_factor, unit = self._unit_factor(ref)
        per_frame, frame_errors, joint_acc = [], [], np.zeros(n_joints)
        for ci, si in path:
            k = pair_lookup[(ci, si)]
            e = float(rel[k])
            joint_acc += joint_err[k] / body_radius[ci]
            c_frame, s_frame = int(ref_idx[ci]), int(stu_idx[si])
            per_frame.append({"coach_frame": c_frame, "student_frame": s_frame, "error": round(e, 4)})
            if e > self.tolerance:
                worst = np.argsort(-joint_err[k])[:3]
                frame_errors.append({
                    "coach_frame": c_frame,
                    "student_frame": s_frame,
                    "error": round(e, 4),
                    "error_percent": round(e * 100, 1),
                    "pa_mpjpe": round(float(joint_err[k].mean()) * unit_factor, 1) if unit_factor else None,
                    "max_angle_error": round(e * 100, 1),
                    "worst_joints": [names[w] for w in worst],
                    "status": "INCORRECT",
                })

        mean_rel = float(np.mean([p["error"] for p in per_frame])) if per_frame else 1.0
        final_score = float(np.clip(1.0 - mean_rel / self.max_error, 0.0, 1.0) * 100.0)
        joint_mean = joint_acc / max(len(path), 1)
        joint_mean_errors = {names[i]: round(float(joint_mean[i]) * 100, 1) for i in range(n_joints)}
        top_joints = [names[i] for i in np.argsort(-joint_mean)[:3]]

        fps = float(student_data.get("fps") or 30.0)
        segments = self._segments(frame_errors, fps)
        error_ratio = len(frame_errors) / max(len(path), 1) * 100
        mean_mm = round(float(np.mean([joint_err[pair_lookup[p]].mean() for p in path])) * unit_factor, 1) if unit_factor else None

        if final_score >= 85:
            quality = "Xuất sắc! Các động tác rất chuẩn xác so với bài mẫu."
        elif final_score >= 70:
            quality = "Khá tốt! Cần chú ý điều chỉnh một số khớp ở các thời điểm then chốt."
        elif final_score >= 50:
            quality = "Đạt yêu cầu cơ bản, tuy nhiên tư thế và biên độ động tác còn nhiều sai lệch."
        else:
            quality = "Chưa đạt. Cần quan sát kỹ video bài mẫu của HLV và luyện tập lại."
        mm_text = f" (PA-MPJPE trung bình {mean_mm} {unit})" if mean_mm is not None else ""
        if segments:
            detail = (f"Phát hiện {len(segments)} đoạn sai ({round(error_ratio, 1)}% thời lượng) lệch quá "
                      f"{int(self.tolerance * 100)}%. Khớp cần chú ý nhất: {', '.join(top_joints)}.")
        else:
            detail = f"Không có thời điểm nào lệch quá ngưỡng {int(self.tolerance * 100)}%."
            top_joints = []
        summary = f"Đánh giá hoàn thành: {round(final_score, 1)}/100 điểm{mm_text}. {detail} {quality}"

        return {
            "final_score": round(final_score, 1),
            "metric": "PA-MPJPE",
            "mean_error": round(mean_rel, 4),
            "mean_pa_mpjpe": mean_mm,
            "unit": unit,
            "warping_path": [(int(ref_idx[c]), int(stu_idx[s])) for c, s in path],
            "frame_errors": frame_errors,
            "segments": segments,
            "per_frame_error": per_frame,
            "joint_mean_errors": joint_mean_errors,
            "top_joints": top_joints,
            "tolerance": self.tolerance,
            "feedback_summary": summary,
        }

    @staticmethod
    def _segments(frame_errors: List[Dict[str, Any]], fps: float) -> List[Dict[str, Any]]:
        segments: List[Dict[str, Any]] = []
        current: List[Dict[str, Any]] = []

        def flush():
            if not current:
                return
            counter = Counter(j for e in current for j in e["worst_joints"])
            errs = [e["error"] for e in current]
            s0, s1 = current[0]["student_frame"], current[-1]["student_frame"]
            segments.append({
                "student_start": s0, "student_end": s1,
                "coach_start": current[0]["coach_frame"], "coach_end": current[-1]["coach_frame"],
                "time_start": round(s0 / fps, 2), "time_end": round(s1 / fps, 2),
                "max_error_percent": round(max(errs) * 100, 1),
                "mean_error_percent": round(float(np.mean(errs)) * 100, 1),
                "worst_joints": [j for j, _ in counter.most_common(3)],
            })

        gap = max(2, int(round(fps * 0.3)))
        for e in frame_errors:
            if current and e["student_frame"] - current[-1]["student_frame"] > gap:
                flush()
                current = []
            current.append(e)
        flush()
        return segments
