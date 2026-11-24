import numpy as np
from typing import Dict, Any, List, Tuple
from ..base.scorer import BaseScorer

try:
    from scipy.spatial.distance import cdist
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

class FastDTWScorer(BaseScorer):
    """
    Thuật toán chấm điểm sử dụng Dynamic Time Warping (DTW).
    Căn chỉnh phi tuyến chuỗi thời gian của Học viên về chuẩn của HLV.
    Đã được tối ưu hóa tính toán ma trận khoảng cách bằng Vectorization / SciPy cdist.
    """

    def __init__(self, angle_tolerance: float = 15.0):
        super().__init__(name="FastDTWScorer")
        self.angle_tolerance = angle_tolerance  # Ngưỡng lệch góc cho phép (độ)

    def _compute_distance_matrix(self, seq_a: np.ndarray, seq_b: np.ndarray) -> np.ndarray:
        """
        Tính ma trận khoảng cách Euclid giữa các vector góc khớp tại từng frame.
        Sử dụng SciPy cdist hoặc Vectorized NumPy để đạt hiệu năng O(1) in C/BLAS thay vì vòng lặp Python.
        """
        if HAS_SCIPY:
            return cdist(seq_a, seq_b, metric="euclidean")
        else:
            # NumPy broadcasting: (N, 1, D) - (1, M, D) -> (N, M, D) -> norm along axis -1
            return np.linalg.norm(seq_a[:, np.newaxis, :] - seq_b[np.newaxis, :, :], axis=-1)

    def _run_dtw(self, dist_matrix: np.ndarray) -> Tuple[float, List[Tuple[int, int]]]:
        """
        Quy hoạch động tìm đường đi chi phí nhỏ nhất (Minimal Cost Warping Path).
        """
        n, m = dist_matrix.shape
        cost = np.full((n, m), np.inf)
        cost[0, 0] = dist_matrix[0, 0]

        for i in range(1, n):
            cost[i, 0] = cost[i - 1, 0] + dist_matrix[i, 0]
        for j in range(1, m):
            cost[0, j] = cost[0, j - 1] + dist_matrix[0, j]

        for i in range(1, n):
            for j in range(1, m):
                cost[i, j] = dist_matrix[i, j] + min(
                    cost[i - 1, j],      # Chèn (Insertion)
                    cost[i, j - 1],      # Xóa (Deletion)
                    cost[i - 1, j - 1]   # Khớp (Match)
                )

        # Truy vết đường đi tối ưu từ điểm cuối về điểm đầu
        i, j = n - 1, m - 1
        path = [(i, j)]
        while i > 0 or j > 0:
            if i == 0:
                j -= 1
            elif j == 0:
                i -= 1
            else:
                min_step = min(cost[i - 1, j], cost[i, j - 1], cost[i - 1, j - 1])
                if min_step == cost[i - 1, j - 1]:
                    i, j = i - 1, j - 1
                elif min_step == cost[i - 1, j]:
                    i -= 1
                else:
                    j -= 1
            path.append((i, j))

        path.reverse()
        normalized_distance = float(cost[-1, -1] / max(len(path), 1))
        return normalized_distance, path

    def evaluate(self, coach_data: Dict[str, Any], student_data: Dict[str, Any]) -> Dict[str, Any]:
        coach_angles = np.array(coach_data.get("joint_angles", []), dtype=np.float32)
        student_angles = np.array(student_data.get("joint_angles", []), dtype=np.float32)

        if coach_angles.size == 0 or student_angles.size == 0:
            return {
                "final_score": 0.0,
                "warping_path": [],
                "frame_errors": [],
                "feedback_summary": "Lỗi: Không phát hiện được dữ liệu khung xương hợp lệ từ video."
            }

        # Đảm bảo dữ liệu 2 chiều (N_frames, N_angles)
        if coach_angles.ndim == 1:
            coach_angles = coach_angles.reshape(-1, 1)
        if student_angles.ndim == 1:
            student_angles = student_angles.reshape(-1, 1)

        dist_matrix = self._compute_distance_matrix(coach_angles, student_angles)
        avg_dist, path = self._run_dtw(dist_matrix)

        # Quy đổi khoảng cách sang thang điểm 100
        # Điểm = max(0, 100 - avg_dist * hệ số phạt)
        final_score = max(0.0, min(100.0, 100.0 - (avg_dist * 2.0)))

        # Phát hiện các frame bị sai lệch vượt ngưỡng cho phép
        frame_errors = []
        for c_idx, s_idx in path:
            if c_idx < len(coach_angles) and s_idx < len(student_angles):
                diff = np.abs(coach_angles[c_idx] - student_angles[s_idx])
                max_err = float(np.max(diff))
                if max_err > self.angle_tolerance:
                    frame_errors.append({
                        "coach_frame": int(c_idx),
                        "student_frame": int(s_idx),
                        "max_angle_error": round(max_err, 2),
                        "status": "INCORRECT"
                    })

        error_ratio = (len(frame_errors) / max(len(path), 1)) * 100
        if final_score >= 85:
            quality = "Xuất sắc! Các động tác rất chuẩn xác so với bài mẫu."
        elif final_score >= 70:
            quality = "Khá tốt! Cần chú ý điều chỉnh một số góc khớp ở các thời điểm then chốt."
        elif final_score >= 50:
            quality = "Đạt yêu cầu cơ bản, tuy nhiên nhịp điệu và biên độ động tác còn nhiều sai lệch."
        else:
            quality = "Chưa đạt. Cần quan sát kỹ video bài mẫu của HLV và luyện tập lại."

        summary = (
            f"Đánh giá hoàn thành: {round(final_score, 1)}/100 điểm. "
            f"Phát hiện {len(frame_errors)} thời điểm ({round(error_ratio, 1)}%) có độ lệch vượt quá {self.angle_tolerance}°. "
            f"{quality}"
        )

        return {
            "final_score": round(final_score, 1),
            "warping_path": path,
            "frame_errors": frame_errors,
            "feedback_summary": summary
        }
