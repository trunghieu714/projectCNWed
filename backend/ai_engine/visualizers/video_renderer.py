import os
import cv2
import numpy as np
from typing import Dict, Any, Optional
from ..base.visualizer import BaseVisualizer

class _FrameStream:
    """Đọc tuần tự một video, cho phép lấy frame có chỉ số không giảm mà không nạp cả video vào RAM."""

    def __init__(self, path: str, size):
        self.cap = cv2.VideoCapture(path)
        self.size = size
        self.index = -1
        self.frame = None

    @property
    def ok(self) -> bool:
        return self.cap.isOpened()

    def get(self, target: int) -> np.ndarray:
        while self.index < target:
            ret, frame = self.cap.read()
            if not ret:
                break
            self.index += 1
            self.frame = frame
        if self.frame is None:
            return np.zeros((self.size[1], self.size[0], 3), dtype=np.uint8)
        return cv2.resize(self.frame, self.size)

    def release(self):
        self.cap.release()

class FusedVideoRenderer(BaseVisualizer):
    """
    Module phụ trách:
    1. Ghép 2 video góc quay của học viên (left/right) thành 1 video song song (Slide 25, FAQ Q6).
    2. Ghép video HLV và HV song song (Side-by-Side) theo warping path DTW, tô đỏ các frame sai
       và xuất file 'fused_output.mp4'.
    """

    def __init__(self, target_fps: int = 25):
        self.target_fps = target_fps

    def _get_video_writer(self, output_path: str, fps: float, width: int, height: int) -> cv2.VideoWriter:
        """Thử dùng codec mp4v (tối ưu Windows/Linux) hoặc avc1 / XVID."""
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        codecs_to_try = ['mp4v', 'avc1', 'XVID'] if os.name == 'nt' else ['avc1', 'mp4v', 'XVID']
        for codec in codecs_to_try:
            fourcc = cv2.VideoWriter_fourcc(*codec)
            out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
            if out.isOpened():
                return out
        return cv2.VideoWriter(output_path, cv2.VideoWriter_fourcc(*'mp4v'), fps, (width, height))

    @staticmethod
    def _make_web_compatible(path: str) -> None:
        try:
            from app.core.video_transcoder import ensure_web_compatible_video
            ensure_web_compatible_video(path)
        except Exception:
            pass

    def merge_two_videos(self, video_left_path: str, video_right_path: str, output_path: str) -> str:
        """Ghép 2 góc quay (trái - phải) của người dùng thành 1 video (dự phòng khi không có FFmpeg)."""
        left = _FrameStream(video_left_path, (640, 480)) if os.path.exists(video_left_path) else None
        right = _FrameStream(video_right_path, (640, 480)) if os.path.exists(video_right_path) else None
        if not left or not right or not left.ok or not right.ok:
            for s in (left, right):
                if s:
                    s.release()
            return self._generate_fallback_video(output_path, 0.0)

        fps = left.cap.get(cv2.CAP_PROP_FPS) or self.target_fps
        out = self._get_video_writer(output_path, fps, 1280, 480)
        for i in range(5400):  # tối đa ~3 phút ở 30fps
            before = (left.index, right.index)
            fl, fr = left.get(i), right.get(i)
            if (left.index, right.index) == before:
                break
            for frame, text in ((fl, "GOC TRAI (LEFT)"), (fr, "GOC PHAI (RIGHT)")):
                cv2.rectangle(frame, (10, 10), (200, 40), (0, 0, 0), -1)
                cv2.putText(frame, text, (15, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            out.write(np.hstack((fl, fr)))
        left.release()
        right.release()
        out.release()
        self._make_web_compatible(output_path)
        return output_path

    def render_fused_video(
        self,
        coach_video_path: str,
        student_video_path: str,
        evaluation_result: Dict[str, Any],
        output_video_path: str
    ) -> str:
        final_score = evaluation_result.get("final_score", 0.0)
        # Warping path theo chỉ số frame video (pipeline đã quy đổi từ chỉ số frame pose)
        path = evaluation_result.get("video_warping_path") or evaluation_result.get("warping_path", [])
        error_frames: Dict[int, str] = evaluation_result.get("video_error_frames") or {
            e.get("student_frame"): f"{e.get('error_percent', e.get('max_angle_error', 0))}%"
            for e in evaluation_result.get("frame_errors", [])
        }
        fps = float(evaluation_result.get("output_fps") or self.target_fps)

        if not os.path.exists(coach_video_path) or not os.path.exists(student_video_path):
            return self._generate_fallback_video(output_video_path, final_score)

        w, h = 640, 480
        coach = _FrameStream(coach_video_path, (w, h))
        student = _FrameStream(student_video_path, (w, h))
        if not coach.ok or not student.ok:
            coach.release()
            student.release()
            return self._generate_fallback_video(output_video_path, final_score)

        if not path:
            n = int(min(coach.cap.get(cv2.CAP_PROP_FRAME_COUNT), student.cap.get(cv2.CAP_PROP_FRAME_COUNT), 1500))
            path = [(i, i) for i in range(max(n, 1))]

        out = self._get_video_writer(output_video_path, fps, w * 2, h)
        written = 0
        for c_idx, s_idx in path[:3000]:
            c_frame = coach.get(int(c_idx)).copy()
            s_frame = student.get(int(s_idx)).copy()
            err = error_frames.get(int(s_idx))
            color = (0, 0, 255) if err else (0, 200, 0)
            status_text = f"LECH {err}" if err else "CHUAN XAC"
            if err:
                cv2.rectangle(s_frame, (0, 0), (w - 1, h - 1), (0, 0, 255), 6)
            fused = np.hstack((c_frame, s_frame))
            cv2.rectangle(fused, (10, 10), (250, 45), (20, 20, 20), -1)
            cv2.putText(fused, "HLV (CHUAN)", (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.rectangle(fused, (w + 10, 10), (w + 360, 45), (20, 20, 20), -1)
            cv2.putText(fused, f"HOC VIEN: {status_text}", (w + 20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            cv2.rectangle(fused, (0, h - 40), (w * 2, h), (0, 0, 0), -1)
            score_color = (0, 255, 0) if final_score >= 80 else ((0, 215, 255) if final_score >= 60 else (0, 0, 255))
            cv2.putText(fused, f"AI SCORE: {final_score}/100", (w - 120, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.8, score_color, 2)
            out.write(fused)
            written += 1
        coach.release()
        student.release()
        out.release()
        if written == 0:
            return self._generate_fallback_video(output_video_path, final_score)
        self._make_web_compatible(output_video_path)
        return output_video_path

    def _generate_fallback_video(self, output_path: str, score: float) -> str:
        """Tạo file placeholder khi video nguồn không đọc được."""
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        out = self._get_video_writer(output_path, 15, 640, 360)
        for _ in range(45):
            frame = np.zeros((360, 640, 3), dtype=np.uint8)
            frame[:, :] = (30, 20, 20)
            cv2.putText(frame, "SKILL ASSESSMENT PLATFORM", (80, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
            cv2.putText(frame, f"AI Motion Score: {score}/100", (160, 190), cv2.FONT_HERSHEY_SIMPLEX, 1.0,
                        (0, 255, 0) if score >= 70 else (0, 165, 255), 2)
            cv2.putText(frame, "Fused DTW Synchronization Preview", (130, 240), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180, 180, 180), 1)
            out.write(frame)
        out.release()
        self._make_web_compatible(output_path)
        return output_path
