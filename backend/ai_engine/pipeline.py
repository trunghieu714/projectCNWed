import logging
import os
from typing import Any, Dict, Optional

import numpy as np

from .base.estimator import BasePoseEstimator
from .base.scorer import BaseScorer
from .base.visualizer import BaseVisualizer
from .factory import AIEngineFactory
from .pose_io import PoseCache, build_pose_result
from .visualizers.html_report import HtmlReportRenderer

logger = logging.getLogger(__name__)
SIDES = ("left", "right")

class SkillAssessmentPipeline:
    """
    Facade Pattern: Cung cấp một giao diện đơn giản duy nhất để thực thi toàn bộ quy trình:
    [Video HLV & HV (1-2 góc quay)] -> [Trích xuất Pose] -> [(Fusion 2 góc)] ->
    [Căn chỉnh & Chấm điểm DTW] -> [Render Video Fused + Báo cáo HTML]
    """

    def __init__(
        self,
        estimator: BasePoseEstimator = None,
        scorer: BaseScorer = None,
        visualizer: BaseVisualizer = None,
        report_renderer: Optional[HtmlReportRenderer] = None,
        pose_cache: Optional[PoseCache] = None,
        calibration_path: Optional[str] = None,
    ):
        # Dependency Injection, nếu không truyền sẽ dùng Factory mặc định
        self.estimator = estimator or AIEngineFactory.create_estimator("mock")
        self.scorer = scorer or AIEngineFactory.create_scorer("dtw")
        self.visualizer = visualizer or AIEngineFactory.create_visualizer("fused_video")
        self.report_renderer = report_renderer or HtmlReportRenderer()
        self.pose_cache = pose_cache
        self.calibration_path = calibration_path

    # ------------------------------------------------------------------------------------------
    def extract(self, video_path: str, use_cache: bool = False) -> Dict[str, Any]:
        """Trích xuất pose; pose video HLV được cache để dùng lại cho mọi bài nộp."""
        if use_cache and self.pose_cache:
            cached = self.pose_cache.load(video_path, self.estimator.model_name)
            if cached is not None:
                return cached
        pose = self.estimator.extract_poses(video_path)
        if use_cache and self.pose_cache and pose.get("joints_3d") is not None:
            try:
                self.pose_cache.save(video_path, self.estimator.model_name, pose)
            except Exception as e:
                logger.warning("Không ghi được cache pose: %s", e)
        return pose

    def _try_fusion(self, poses: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Fusion 2 bộ pose 2D thành 3D nếu có file hiệu chỉnh camera (Slide 10)."""
        if not self.calibration_path or not os.path.exists(self.calibration_path):
            return None
        left, right = poses.get("left"), poses.get("right")
        if not left or not right or left.get("keypoints_2d") is None or right.get("keypoints_2d") is None:
            return None
        try:
            from .fusion.two_view import fuse_two_views, load_projection_matrices
            p1, p2 = load_projection_matrices(self.calibration_path)
            fused = fuse_two_views(left, right, p1, p2)
            res = build_pose_result(fused["joints_3d"], fps=left["fps"], source="two-view fusion",
                                    frame_indices=fused["frame_indices"])
            res["time_offset"] = fused["time_offset"]
            return res
        except Exception as e:
            logger.warning("Fusion 2 góc quay thất bại, chấm riêng từng góc: %s", e)
            return None

    @staticmethod
    def _to_video_frames(result: Dict[str, Any], coach_pose: Dict[str, Any], student_pose: Dict[str, Any]) -> None:
        """Quy đổi chỉ số frame pose (có thể đã lấy mẫu thưa) sang chỉ số frame video để render."""
        c_map = coach_pose.get("frame_indices") or []
        s_map = student_pose.get("frame_indices") or []

        def cv(i): return int(c_map[min(i, len(c_map) - 1)]) if c_map else int(i)
        def sv(i): return int(s_map[min(i, len(s_map) - 1)]) if s_map else int(i)

        result["video_warping_path"] = [(cv(c), sv(s)) for c, s in result.get("warping_path", [])]
        result["video_error_frames"] = {
            sv(e["student_frame"]): f"{e.get('error_percent', e.get('max_angle_error', 0))}%"
            for e in result.get("frame_errors", [])
        }
        result["output_fps"] = float(student_pose.get("fps") or 25.0)

    # ------------------------------------------------------------------------------------------
    def run_multi_view_assessment(
        self,
        coach_videos: Dict[str, Optional[str]],
        student_videos: Dict[str, Optional[str]],
        output_dir: str = "storage/outputs",
        title: str = "Kết quả chấm điểm động tác",
    ) -> Dict[str, Any]:
        """
        coach_videos / student_videos: {"left": path, "right": path} (có thể chỉ 1 góc).
        Mỗi góc quay của HV được so với góc tương ứng của HLV (hoặc góc duy nhất HLV có).
        """
        os.makedirs(output_dir, exist_ok=True)
        coach_any = next((coach_videos[s] for s in SIDES if coach_videos.get(s)), None)
        student_sides = [s for s in SIDES if student_videos.get(s)]
        if not coach_any or not student_sides:
            raise ValueError("Thiếu video HLV hoặc video HV để chấm điểm")

        student_poses = {s: self.extract(student_videos[s]) for s in student_sides}
        coach_paths = {s: coach_videos.get(s) or coach_any for s in student_sides}
        coach_poses = {s: self.extract(coach_paths[s], use_cache=True) for s in student_sides}

        sides: Dict[str, Dict[str, Any]] = {}
        fused_student = self._try_fusion(student_poses) if len(student_sides) == 2 else None
        fused_coach = self._try_fusion(coach_poses) if fused_student and coach_videos.get("right") else None
        if fused_student is not None:
            coach_ref = fused_coach or coach_poses["left"]
            res = self.scorer.evaluate(coach_ref, fused_student)
            res["pose_source"] = fused_student["source"]
            self._to_video_frames(res, coach_ref, fused_student)
            sides["fused"] = res
        else:
            for s in student_sides:
                res = self.scorer.evaluate(coach_poses[s], student_poses[s])
                res["pose_source"] = student_poses[s].get("source", self.estimator.model_name)
                self._to_video_frames(res, coach_poses[s], student_poses[s])
                sides[s] = res

        final_score = round(float(np.mean([r["final_score"] for r in sides.values()])), 1)
        primary_side = next(iter(sides))
        primary = sides[primary_side]
        render_side = primary_side if primary_side in SIDES else "left"

        output_video_path = os.path.join(output_dir, "fused_output.mp4")
        saved_video_path = self.visualizer.render_fused_video(
            coach_video_path=coach_paths.get(render_side, coach_any),
            student_video_path=student_videos[render_side],
            evaluation_result=primary,
            output_video_path=output_video_path,
        )

        if len(sides) > 1:
            parts = [f"{'Bên trái' if s == 'left' else 'Bên phải'}: {r['final_score']}" for s, r in sides.items()]
            summary = f"Điểm tổng hợp {final_score}/100 ({'; '.join(parts)}). " + primary["feedback_summary"]
        else:
            summary = primary["feedback_summary"]

        result = {
            "score": final_score,
            "summary": summary,
            "metric": primary.get("metric", "DTW"),
            "errors": primary.get("frame_errors", []),
            "fused_video_url": saved_video_path,
            "warping_path": primary.get("warping_path", []),
            "video_warping_path": primary.get("video_warping_path", []),
            "output_fps": primary.get("output_fps"),
            "warping_path_length": len(primary.get("warping_path", [])),
            "pose_source": primary.get("pose_source"),
            "sides": sides,
        }
        report_path = os.path.join(output_dir, "report.html")
        result["report_html"] = self.report_renderer.render(result, report_path, title=title)
        result["report_path"] = report_path
        return result

    def run_assessment(self, coach_video_path: str, student_video_path: str, output_dir: str = "storage/outputs") -> Dict[str, Any]:
        """Giao diện cũ: chấm 1 video HV với 1 video HLV."""
        return self.run_multi_view_assessment({"left": coach_video_path}, {"left": student_video_path}, output_dir)
