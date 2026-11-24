import logging
from typing import Any, Dict
import numpy as np
from ..base.estimator import BasePoseEstimator
from ..pose_io import PoseNotAvailable, build_pose_result, coco_to_h36m

logger = logging.getLogger(__name__)

class YoloPoseEstimator(BasePoseEstimator):
    """
    Pose 2D bằng YOLO pose (YOLO26x theo đề tài - Slide 8, 10) qua thư viện `ultralytics`.

    Kết quả là 17 khớp H36M trên mặt phẳng ảnh (z = 0), đã chuẩn hóa tâm xương chậu và tỉ lệ
    thân người. Khi có 2 góc quay và file hiệu chỉnh camera, pipeline sẽ fusion 2 bộ pose 2D
    thành pose 3D (ai_engine/fusion/two_view.py). Muốn pose 3D từ 1 video hãy dùng WHAM/GVHMR
    (estimator "precomputed" hoặc "remote").
    """

    def __init__(self, weights: str = "yolo26x-pose.pt", sample_fps: float = 10.0, config: Dict[str, Any] = None):
        super().__init__(model_name="YOLOPose", config=config)
        self.weights = weights
        self.sample_fps = sample_fps
        self.model = None

    def load_model(self) -> None:
        try:
            from ultralytics import YOLO
        except ImportError as e:
            raise PoseNotAvailable("Chưa cài thư viện ultralytics (pip install ultralytics)") from e
        try:
            self.model = YOLO(self.weights)
        except Exception as e:
            raise PoseNotAvailable(f"Không nạp được trọng số YOLO {self.weights}: {e}") from e
        self.is_loaded = True

    def extract_poses(self, video_path: str) -> Dict[str, Any]:
        import cv2
        if not self.is_loaded:
            self.load_model()
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise PoseNotAvailable(f"Không mở được video {video_path}")
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        step = max(1, int(round(fps / self.sample_fps)))
        kps, confs, frame_indices = [], [], []
        idx = 0
        last = None
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if idx % step == 0:
                res = self.model.predict(frame, verbose=False)[0]
                pts = None
                if res.keypoints is not None and len(res.keypoints) > 0:
                    boxes = res.boxes.xywh.cpu().numpy() if res.boxes is not None else None
                    person = int(np.argmax(boxes[:, 2] * boxes[:, 3])) if boxes is not None and len(boxes) else 0
                    xy = res.keypoints.xy.cpu().numpy()[person]
                    cf = res.keypoints.conf.cpu().numpy()[person] if res.keypoints.conf is not None else np.ones(len(xy))
                    pts = (xy, cf)
                if pts is None and last is not None:
                    pts = last  # giữ pose frame trước khi mất người trong 1-2 frame
                if pts is not None:
                    kps.append(pts[0])
                    confs.append(pts[1])
                    frame_indices.append(idx)
                    last = pts
            idx += 1
        cap.release()
        if len(kps) < 3:
            raise PoseNotAvailable("YOLO không phát hiện được người trong video")

        kp2d = coco_to_h36m(np.asarray(kps))  # (N, 17, 2)
        conf = coco_to_h36m(np.asarray(confs)[..., None])[..., 0]
        # Chuẩn hóa: tâm xương chậu, chia cho chiều dài thân (chậu -> ngực), trục y hướng lên
        centered = kp2d - kp2d[:, :1]
        torso = np.linalg.norm(kp2d[:, 8] - kp2d[:, 0], axis=-1, keepdims=True)
        scale = np.median(torso) if np.median(torso) > 1e-6 else 1.0
        norm = centered / scale
        norm[..., 1] *= -1
        joints = np.concatenate([norm, np.zeros(norm.shape[:-1] + (1,))], axis=-1)
        result = build_pose_result(joints, fps=fps / step, source=f"yolo:{self.weights}",
                                   frame_indices=frame_indices, keypoints_2d=kp2d, dims=2)
        result["keypoints_conf"] = conf
        return result
