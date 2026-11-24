#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DTW PKL grader + static HTML visualization report.

Final report: merge the visual and comprehensive ideas into one clear report, and for two-side grading show separate Left/Right tabs so each tab only contains that side.

Important changes:
- When both left and right videos are graded, the HTML report now has 2 tabs: one for Left and one for Right. Each tab only shows that side.
- The report keeps the visual skeleton/pose points (visual_report idea) and the human-readable distance explanation (comprehensive_report idea) in the same place.
- Default detail mode is "failures" to match the professor requirement of showing the error list. Users can still set POSE_GRADER_DETAIL_MODE=all or sample if needed.
- The visual guide is kept clean: the reference pose and student pose are drawn in their own images, without cross-camera overlay; exact cm/mm distances are shown in the table below.

Important fix:
- NEVER use SMPL pose/rotation parameters such as pred_pose/body_pose/theta
  as if they were 3D joint coordinates. Those arrays are rotations, usually
  [T,72] or [T,24,3], and drawing them creates the star/triangle skeleton that
  appears shifted away from the person.
- Prefer real joint/keypoint arrays, or compute joints from vertices+J_regressor,
  or compute joints from SMPL parameters through smplx + SMPL model files.
- If SMPL vertices are available, derive a sparse pose skeleton from the mesh and
  project it using calib_left/calib_right intrinsics instead of drawing the mesh.
- The report never draws all 6890 SMPL vertices/outline.

Input from stdin (4 lines):
1) reference folder
2) student folder
3) threshold
4) metric: MPJPE or PA-MPJPE

Expected folders can contain:
- left/right pose PKL files (or trai/phai)
- left/right video files (.mp4/.mov/.avi/.mkv)
- optional left/right calibration txt files with: fx fy cx cy

Output:
- prints final score and textual error summary
- creates a static HTML report with image rows for checked frames; true failures are marked clearly

Install:
    python -m pip install numpy joblib opencv-python
    python -m pip install mediapipe  # strongly recommended for correct report overlay
    python -m pip install chumpy    # needed only if loading legacy SMPL_NEUTRAL.pkl

Useful environment variables:
    SMPL_MODEL_FILE=E:\\SMPL_models\\SMPL_NEUTRAL.pkl
    POSE_GRADER_DISTANCE_TO_MM=1000   # default: SMPL/model unit is meter, so 1.0 -> 1000 mm
    POSE_GRADER_DETAIL_MODE=failures   # final/professor report: only real error frames
    POSE_GRADER_SAMPLE_EVERY=25        # used only when DETAIL_MODE=sample
    POSE_GRADER_SHOW_TARGET_GUIDE=0    # final cross-view-safe default: do not overlay reference pose or draw correction arrows
    POSE_GRADER_TOP_GUIDE_JOINTS=5     # number of worst joints to list in the explanation table
"""

import os
import sys
import cv2
import html
import itertools
import math
import json
import pickle
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass

import joblib
import numpy as np

# -----------------------------
# Settings
# -----------------------------
ROOT_CENTER_MPJPE = False  # keep same behavior as previous script unless changed
# Number of detailed failing-frame rows to include in HTML.
# Default is ALL failing frames, matching the older report behavior.
# You can set POSE_GRADER_MAX_HTML_ROWS=50 for a shorter report, or 'all'/empty for all.
def _read_max_html_rows():
    val = os.environ.get('POSE_GRADER_MAX_HTML_ROWS', '').strip().lower()
    if val in ('', 'none', 'all', '0', '-1'):
        return None
    try:
        return max(1, int(val))
    except Exception:
        return None
MAX_HTML_ROWS = _read_max_html_rows()

# Detailed table mode.
# - failures: show only frames whose MPJPE/PA-MPJPE is above threshold. This is the default and matches the requirement of showing the error list.
# - all/sample can include passing rows only when POSE_GRADER_ALLOW_PASS_ROWS=1.
# - professor-facing final reports keep POSE_GRADER_ALLOW_PASS_ROWS=0 so tables remain true error lists.
def _read_detail_mode():
    val = os.environ.get("POSE_GRADER_DETAIL_MODE", "failures").strip().lower()
    if val not in ("all", "failures", "sample"):
        val = "failures"
    return val

def _read_sample_every():
    try:
        return max(1, int(os.environ.get("POSE_GRADER_SAMPLE_EVERY", "25")))
    except Exception:
        return 25

DETAIL_MODE = _read_detail_mode()
SAMPLE_EVERY = _read_sample_every()
# Final report table policy. Professor requested "danh sách lỗi".
# Therefore PASS/Đạt rows are hidden by default even if DETAIL_MODE=sample/all.
# Set POSE_GRADER_ALLOW_PASS_ROWS=1 only for private debugging/demo, not for final submission.
ALLOW_PASS_ROWS = os.environ.get("POSE_GRADER_ALLOW_PASS_ROWS", "0").strip().lower() in ("1", "true", "yes", "on")

# Default overlay mode is intentionally conservative. For professor-facing reports
# we prefer a clean pose-joint skeleton on the person over a mathematically raw
# projection that may be wrong when crop/camera metadata is missing. Set
# POSE_GRADER_OVERLAY_MODE=projection only for debugging raw projection.
# Options: fit, auto_safe, projection.
OVERLAY_MODE = os.environ.get("POSE_GRADER_OVERLAY_MODE", "mediapipe").strip().lower()
VIS_BACKEND = os.environ.get("POSE_GRADER_VIS_BACKEND", OVERLAY_MODE).strip().lower()
IMAGE_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
PKL_EXTS = {".pkl", ".pickle"}
TXT_EXTS = {".txt"}
LEFT_KEYWORDS = ["left", "trai"]
RIGHT_KEYWORDS = ["right", "phai"]

# Human-readable distance display. SMPL vertices are usually stored in meters,
# while MPJPE/PA-MPJPE are conventionally explained in millimeters. Therefore
# the default conversion is raw_distance * 1000 = millimeters. If your PKL is
# already in millimeters, run: set POSE_GRADER_DISTANCE_TO_MM=1
DISTANCE_TO_MM = float(os.environ.get("POSE_GRADER_DISTANCE_TO_MM", "1000"))
DISTANCE_DISPLAY_NOTE = os.environ.get(
    "POSE_GRADER_DISTANCE_NOTE",
    "Mặc định quy đổi theo SMPL/meters: 1 đơn vị tọa độ = 1000 mm. Nếu dữ liệu PKL đã ở mm, đặt POSE_GRADER_DISTANCE_TO_MM=1."
)

# DTW search window. A moderate Sakoe-Chiba style band keeps the alignment
# close to the same progress point in both videos, speeds up long samples, and
# avoids unrealistic matches between very distant time points. Set to 0 for full DTW.
def _read_dtw_window_ratio():
    try:
        return max(0.0, float(os.environ.get("POSE_GRADER_DTW_WINDOW_RATIO", "0.12")))
    except Exception:
        return 0.12
DTW_WINDOW_RATIO = _read_dtw_window_ratio()
# Cost metric used only inside the DTW search. The final score is still computed
# with the metric chosen by the user. MPJPE is much faster for long videos; set
# POSE_GRADER_DTW_COST_METRIC=PA-MPJPE if exact PA-based DTW search is needed.
DTW_COST_METRIC = os.environ.get("POSE_GRADER_DTW_COST_METRIC", "MPJPE").strip().upper()
if DTW_COST_METRIC not in ("MPJPE", "PA-MPJPE"):
    DTW_COST_METRIC = "MPJPE"


# Visualization controls: combine the strengths of visual_report and
# comprehensive_report in one HTML report. Important professor fix:
# do NOT overlay the reference skeleton onto the student image by default, because
# the two videos can be captured from different viewpoints. Overlaying two
# different camera views can create misleading crossing lines. The report now
# draws the standard pose on the left image, the student pose on the right image,
# and only marks the student's worst joints with small red rings; exact cm/mm
# distances remain in the table below.
SHOW_TARGET_GUIDE = os.environ.get("POSE_GRADER_SHOW_TARGET_GUIDE", "0").strip().lower() not in ("0", "false", "no", "off")
def _read_top_guide_joints():
    try:
        return max(1, int(os.environ.get("POSE_GRADER_TOP_GUIDE_JOINTS", "5")))
    except Exception:
        return 5
TOP_GUIDE_JOINTS = _read_top_guide_joints()

def _read_image_arrow_joints():
    try:
        return max(0, int(os.environ.get("POSE_GRADER_IMAGE_ARROW_JOINTS", "0")))
    except Exception:
        return 0
IMAGE_ARROW_JOINTS = _read_image_arrow_joints()

# Keep the image clean. Distances are listed below the image, so the image only
# uses small red circles only when explicitly enabled; no arrows are drawn in the final cross-view-safe report.
CLEAN_IMAGE_GUIDE = os.environ.get("POSE_GRADER_CLEAN_IMAGE_GUIDE", "1").strip().lower() not in ("0", "false", "no")
DRAW_JOINT_LABELS = os.environ.get("POSE_GRADER_DRAW_JOINT_LABELS", "1").strip().lower() not in ("0", "false", "no", "off")

# Final report polish: keep the HTML student-facing/professor-facing, not debug-like.
# These defaults remove big English/debug labels from the images and hide raw internal
# values unless explicitly requested.
DRAW_IMAGE_LABELS = os.environ.get("POSE_GRADER_DRAW_IMAGE_LABELS", "0").strip().lower() not in ("0", "false", "no", "off")
SHOW_RAW_VALUES = os.environ.get("POSE_GRADER_SHOW_RAW_VALUES", "0").strip().lower() not in ("0", "false", "no", "off")
SHOW_ENGLISH_JOINT_NAMES = os.environ.get("POSE_GRADER_SHOW_ENGLISH_JOINT_NAMES", "0").strip().lower() not in ("0", "false", "no", "off")
def _read_report_image_height():
    try:
        return max(420, int(os.environ.get("POSE_GRADER_REPORT_IMAGE_HEIGHT", "720")))
    except Exception:
        return 720
REPORT_IMAGE_HEIGHT = _read_report_image_height()

# SMPL 24-joint names. These names are used only for user-facing explanations.
# The order follows the common SMPL 24-joint regressor order.
SMPL24_JOINT_NAMES = [
    ("Xương chậu", "pelvis"),
    ("Hông trái", "left hip"),
    ("Hông phải", "right hip"),
    ("Cột sống dưới", "lower spine"),
    ("Gối trái", "left knee"),
    ("Gối phải", "right knee"),
    ("Cột sống giữa", "middle spine"),
    ("Cổ chân trái", "left ankle"),
    ("Cổ chân phải", "right ankle"),
    ("Cột sống trên", "upper spine"),
    ("Bàn chân trái", "left foot"),
    ("Bàn chân phải", "right foot"),
    ("Cổ/ngực", "neck/chest"),
    ("Xương đòn trái", "left collar"),
    ("Xương đòn phải", "right collar"),
    ("Đầu", "head"),
    ("Vai trái", "left shoulder"),
    ("Vai phải", "right shoulder"),
    ("Khuỷu tay trái", "left elbow"),
    ("Khuỷu tay phải", "right elbow"),
    ("Cổ tay trái", "left wrist"),
    ("Cổ tay phải", "right wrist"),
    ("Bàn tay trái", "left hand"),
    ("Bàn tay phải", "right hand"),
]

# Common skeletons (fallback if joint count supports them)
SKELETON_17 = [
    (0,1),(1,2),(2,3),
    (0,4),(4,5),(5,6),
    (0,7),(7,8),(8,9),(9,10),
    (8,11),(11,12),(12,13),
    (8,14),(14,15),(15,16),
]
SKELETON_16 = [
    (0,1),(1,2),(2,3),
    (0,4),(4,5),(5,6),
    (0,7),(7,8),(8,9),
    (7,10),(10,11),(11,12),
    (7,13),(13,14),(14,15),
]

# Common SMPL 24-joint topology:
# pelvis, L/R hip, spine, L/R knee, spine, L/R ankle, spine, L/R foot, neck,
# L/R collar, head, L/R shoulder, L/R elbow, L/R wrist, L/R hand.
SKELETON_SMPL_24 = [
    # legs and feet
    (0,1),(1,4),(4,7),(7,10),
    (0,2),(2,5),(5,8),(8,11),
    # spine and head
    (0,3),(3,6),(6,9),(9,12),(12,15),
    # shoulders, arms, wrists, hands
    (12,13),(13,16),(16,18),(18,20),(20,22),
    (12,14),(14,17),(17,19),(19,21),(21,23),
    # extra stable connectors so the body is easier to read visually
    (1,2),(10,11),(13,14),(16,17),
]

# -----------------------------
# Utilities
# -----------------------------
def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

def normalize_name(path: str) -> str:
    return os.path.basename(path).lower()

def is_left_name(name: str) -> bool:
    n = name.lower()
    return any(k in n for k in LEFT_KEYWORDS)

def is_right_name(name: str) -> bool:
    n = name.lower()
    return any(k in n for k in RIGHT_KEYWORDS)

def as_array(x: Any) -> np.ndarray:
    return np.asarray(x)

# -----------------------------
# Loading PKL / SMPL-aware pose extraction
# -----------------------------
@dataclass
class PoseData:
    """Container for the data needed by the grader.

    joints3d is always present and is used for MPJPE/PA-MPJPE.
    joints2d/camera/crop metadata are optional and are used only for drawing
    the overlay on the original video frames.
    """
    joints3d: np.ndarray
    joints2d: Optional[np.ndarray] = None
    vertices3d: Optional[np.ndarray] = None  # [T,6890,3] optional SMPL mesh; used only to derive sparse pose joints for overlay
    camera: Optional[np.ndarray] = None
    bbox: Optional[np.ndarray] = None       # [T,4], xyxy or xywh depending on source
    center: Optional[np.ndarray] = None     # [T,2], crop/person center in full-image pixels
    scale: Optional[np.ndarray] = None      # [T] or [T,2], common HMR/SPIN scale
    crop_size: Optional[np.ndarray] = None  # [T] or scalar, usually 224/256
    source: str = "unknown"

VERTEX_NAME_HINTS = ("vert", "vertex", "vertices", "mesh", "v_template", "smpl_vertices")
JOINT3D_NAME_HINTS = (
    "joints3d", "joint3d", "joints_3d", "joint_3d", "keypoints3d", "keypoints_3d",
    "kp3d", "pose3d", "pose_3d", "pred_joints", "pred_3d_joints", "joint_locations",
    "j3d", "world_coord"
)
JOINT2D_NAME_HINTS = (
    "joints2d", "joint2d", "joints_2d", "joint_2d", "keypoints2d", "keypoints_2d",
    "kp2d", "pose2d", "pose_2d", "j2d", "image_coord", "img_coord"
)
CAMERA_NAME_HINTS = ("pred_cam", "camera", "cam", "weak_persp", "cam_t", "camera_translation", "transl")
# Metadata needed to convert crop-space SMPL/HMR projection back to full-video pixels.
# This is the missing piece that usually causes the skeleton to fly to the wall/corner.
BBOX_NAME_HINTS = ("bbox", "bboxes", "box", "boxes", "person_box", "person_bbox", "crop_bbox")
CENTER_NAME_HINTS = ("center", "centers", "crop_center", "bbox_center", "person_center")
SCALE_NAME_HINTS = ("scale", "scales", "crop_scale", "bbox_scale", "person_scale")
CROP_SIZE_NAME_HINTS = ("crop_size", "img_res", "input_res", "image_size", "res")
REGRESSOR_NAME_HINTS = ("j_regressor", "joint_regressor", "joints_regressor")
NON_JOINT_NAME_HINTS = (
    "beta", "betas", "shape", "pred_shape", "smpl_shape",
    "camera", "pred_cam", "cam_t", "weak_persp", "focal", "intrinsic",
    "bbox", "box", "center", "scale", "crop", "img_res", "image_size",
    "conf", "score", "scores", "valid", "mask", "gender", "frame", "id"
)
ROTATION_NAME_HINTS = (
    "body_pose", "global_orient", "rotmat", "rotation", "axis_angle",
    "theta", "thetas", "pred_pose", "smpl_pose", "poses", "pose_params",
    "full_pose", "root_orient", "orient", "rvec"
)


def load_pickle(path: str) -> Any:
    with open(path, "rb") as f:
        header = f.read(32)
    if b"ftyp" in header:
        raise ValueError(f"{path} looks like a video file, not a pickle pose file.")

    try:
        with open(path, "rb") as f:
            return pickle.load(f)
    except Exception:
        try:
            return joblib.load(path)
        except Exception:
            arr = np.load(path, allow_pickle=True)
            if hasattr(arr, "item") and getattr(arr, "shape", None) == ():
                return arr.item()
            return arr


def _as_numeric_array(x: Any) -> Optional[np.ndarray]:
    try:
        arr = np.asarray(x)
    except Exception:
        return None
    if arr.dtype == object:
        return None
    if not np.issubdtype(arr.dtype, np.number):
        return None
    return arr


def _sequence_points(arr: np.ndarray, dims: int, max_points: int = 200) -> Optional[np.ndarray]:
    """Convert common array layouts to [T, J, dims], but reject SMPL vertices."""
    arr = np.asarray(arr)
    if arr.ndim == 4 and arr.shape[1] == 1:
        arr = arr[:, 0]

    if arr.ndim == 3:
        # [T, J, C]
        if arr.shape[-1] >= dims and arr.shape[1] <= max_points:
            return arr[..., :dims].astype(float)
        # [T, C, J]
        if arr.shape[1] >= dims and arr.shape[2] <= max_points:
            return np.transpose(arr[:, :dims, :], (0, 2, 1)).astype(float)
        # [C, J, T]
        if arr.shape[0] >= dims and arr.shape[0] <= 4 and arr.shape[1] <= max_points:
            return np.transpose(arr[:dims, :, :], (2, 1, 0)).astype(float)

    if arr.ndim == 2:
        # one frame [J, C]
        if arr.shape[1] >= dims and arr.shape[0] <= max_points:
            return arr[None, :, :dims].astype(float)
        # one frame [C, J]
        if arr.shape[0] >= dims and arr.shape[0] <= 4 and arr.shape[1] <= max_points:
            return arr[:dims, :].T[None, :, :].astype(float)
        # flattened sequence [T, J*dims]
        if arr.shape[1] % dims == 0:
            j = arr.shape[1] // dims
            if 5 <= j <= max_points:
                return arr.reshape(arr.shape[0], j, dims).astype(float)

    return None


def _sequence_vertices(arr: np.ndarray) -> Optional[np.ndarray]:
    arr = np.asarray(arr)
    if arr.ndim == 4 and arr.shape[1] == 1:
        arr = arr[:, 0]
    if arr.ndim == 3 and arr.shape[-1] >= 3 and arr.shape[1] > 1000:
        return arr[..., :3].astype(float)
    if arr.ndim == 2 and arr.shape[1] >= 3 and arr.shape[0] > 1000:
        return arr[None, :, :3].astype(float)
    return None


def _sequence_camera(arr: np.ndarray) -> Optional[np.ndarray]:
    arr = np.asarray(arr)
    if arr.ndim == 1 and arr.size in (3, 4):
        return arr[None, :].astype(float)
    if arr.ndim == 2 and arr.shape[1] in (3, 4):
        return arr.astype(float)
    if arr.ndim == 3 and arr.shape[1] == 1 and arr.shape[2] in (3, 4):
        return arr[:, 0, :].astype(float)
    return None


def _sequence_bbox(arr: np.ndarray) -> Optional[np.ndarray]:
    arr = np.asarray(arr)
    if arr.ndim == 1 and arr.size >= 4:
        return arr[None, :4].astype(float)
    if arr.ndim == 2 and arr.shape[1] >= 4:
        return arr[:, :4].astype(float)
    if arr.ndim == 3 and arr.shape[1] == 1 and arr.shape[2] >= 4:
        return arr[:, 0, :4].astype(float)
    return None


def _sequence_center(arr: np.ndarray) -> Optional[np.ndarray]:
    arr = np.asarray(arr)
    if arr.ndim == 1 and arr.size >= 2:
        return arr[None, :2].astype(float)
    if arr.ndim == 2 and arr.shape[1] >= 2:
        return arr[:, :2].astype(float)
    if arr.ndim == 3 and arr.shape[1] == 1 and arr.shape[2] >= 2:
        return arr[:, 0, :2].astype(float)
    return None


def _sequence_scale(arr: np.ndarray) -> Optional[np.ndarray]:
    arr = np.asarray(arr)
    if arr.ndim == 0:
        return arr.reshape(1).astype(float)
    if arr.ndim == 1:
        return arr.astype(float)
    if arr.ndim == 2 and arr.shape[1] in (1, 2):
        return arr.astype(float)
    if arr.ndim == 3 and arr.shape[1] == 1 and arr.shape[2] in (1, 2):
        return arr[:, 0, :].astype(float)
    return None


def _stack_frame_dict_values(lst: List[Any]) -> List[Tuple[str, np.ndarray]]:
    """Handle PKLs saved as list[frame_dict]."""
    if not lst or not all(isinstance(x, dict) for x in lst):
        return []
    keys = set(lst[0].keys())
    for d in lst[1:]:
        keys &= set(d.keys())
    stacked = []
    for k in keys:
        vals = []
        ok = True
        for d in lst:
            arr = _as_numeric_array(d.get(k))
            if arr is None:
                ok = False
                break
            vals.append(arr)
        if ok:
            try:
                stacked.append((str(k), np.stack(vals, axis=0)))
            except Exception:
                pass
    return stacked


def _collect_arrays(obj: Any, path: str = "root", depth: int = 0) -> List[Tuple[str, np.ndarray]]:
    """Collect numeric arrays with their key path so we can rank them safely."""
    if depth > 7:
        return []
    found: List[Tuple[str, np.ndarray]] = []

    arr = _as_numeric_array(obj)
    if arr is not None:
        found.append((path, arr))
        return found

    if isinstance(obj, dict):
        for k, v in obj.items():
            found.extend(_collect_arrays(v, f"{path}.{k}", depth + 1))
    elif isinstance(obj, (list, tuple)):
        found.extend(_stack_frame_dict_values(list(obj)))
        # If it is a list of arrays, try stacking it as a sequence.
        if obj and not isinstance(obj[0], dict):
            vals = []
            ok = True
            for item in obj:
                a = _as_numeric_array(item)
                if a is None:
                    ok = False
                    break
                vals.append(a)
            if ok:
                try:
                    found.append((path, np.stack(vals, axis=0)))
                except Exception:
                    pass
        # Continue recursive search too, but cap the list to avoid huge traversal.
        for i, v in enumerate(list(obj)[:30]):
            found.extend(_collect_arrays(v, f"{path}[{i}]", depth + 1))
    return found


def _name_has(path: str, hints: Tuple[str, ...]) -> bool:
    p = path.lower().replace("-", "_")
    return any(h in p for h in hints)


def _looks_like_rotation_pose(path: str, arr: np.ndarray) -> bool:
    """Return True for SMPL pose/rotation arrays, not joint coordinates.

    This is the key professor fix. Arrays named pred_pose/body_pose/theta/pose
    are usually axis-angle or rotation-matrix parameters. They may have shapes
    like [T,72], [T,24,3], or [T,24,3,3]. They are NOT joint xyz locations.
    Drawing them creates the star-shaped/flying skeleton seen in the bad report.
    """
    p = path.lower().replace("-", "_")
    arr = np.asarray(arr)

    # Explicit 3D pose/keypoint names are allowed, e.g. pose_3d.
    explicit_joint_name = _name_has(p, JOINT3D_NAME_HINTS) or "joint" in p or "keypoint" in p or "kp3d" in p
    explicit_pose3d_name = "pose_3d" in p or "pose3d" in p

    rotation_name = _name_has(p, ROTATION_NAME_HINTS)
    generic_pose_name = ("pose" in p or "theta" in p or "orient" in p) and not explicit_pose3d_name

    if (rotation_name or generic_pose_name) and not explicit_joint_name:
        return True

    # Shape-based rejection for common SMPL pose encodings.
    if arr.ndim == 2 and arr.shape[1] in (63, 69, 72, 75, 85, 144, 156, 165, 207, 216):
        if rotation_name or generic_pose_name:
            return True
    if arr.ndim == 3 and arr.shape[1] in (21, 23, 24, 52, 55) and arr.shape[2] == 3:
        if rotation_name or generic_pose_name:
            return True
    if arr.ndim == 4 and arr.shape[-2:] == (3, 3):
        if rotation_name or generic_pose_name:
            return True
    return False


def _rank_joint3d_candidate(path: str, arr: np.ndarray) -> int:
    p = path.lower()
    if _name_has(p, VERTEX_NAME_HINTS) or _name_has(p, REGRESSOR_NAME_HINTS) or _name_has(p, NON_JOINT_NAME_HINTS):
        return -9999
    if _looks_like_rotation_pose(path, arr):
        return -9999
    pts = _sequence_points(arr, 3)
    if pts is None:
        return -9999
    j = pts.shape[1]

    # Require a real joint/keypoint/coordinate hint. This prevents unrelated
    # small arrays such as betas [T,10] or pred_cam [T,3] from being reshaped
    # into fake joints.
    has_joint_hint = _name_has(p, JOINT3D_NAME_HINTS) or "joint" in p or "keypoint" in p or "kp3d" in p or "xyz" in p or "coord" in p
    if not has_joint_hint:
        return -9999

    rank = 0
    if _name_has(p, JOINT3D_NAME_HINTS):
        rank += 1000
    if "smpl" in p and "joint" in p:
        rank += 200
    if "joint" in p or "keypoint" in p or "kp3d" in p:
        rank += 120
    # Prefer normal pose joint counts. SMPL is usually 24; many detectors use
    # 14/16/17/25/49. Mesh vertices are rejected elsewhere.
    if j in (14, 15, 16, 17, 18, 19, 21, 22, 24, 25, 49):
        rank += 120
    elif 14 <= j <= 30:
        rank += 80
    elif 31 <= j <= 80:
        rank += 40
    else:
        rank += 10
    rank += min(pts.shape[0], 100)
    return rank


def _rank_joint2d_candidate(path: str, arr: np.ndarray) -> int:
    p = path.lower()
    if _name_has(p, VERTEX_NAME_HINTS) or _name_has(p, ROTATION_NAME_HINTS) or _name_has(p, REGRESSOR_NAME_HINTS) or _name_has(p, NON_JOINT_NAME_HINTS):
        return -9999

    # IMPORTANT FIX: do not treat 3D joints as 2D joints just because their last
    # dimension has x/y/z. The old v2 script could select joints3d[:, :, :2]
    # as image pixels. Those values are usually small SMPL/model coordinates,
    # so the skeleton is drawn in the top-left corner or hidden under the label.
    # Only use a candidate as direct 2D if its key name explicitly looks 2D.
    if _name_has(p, JOINT3D_NAME_HINTS) and not _name_has(p, JOINT2D_NAME_HINTS):
        return -9999
    if not _name_has(p, JOINT2D_NAME_HINTS):
        return -9999

    pts = _sequence_points(arr, 2)
    if pts is None:
        return -9999
    rank = 0
    if _name_has(p, JOINT2D_NAME_HINTS):
        rank += 1000
    if "joint" in p or "keypoint" in p or "kp2d" in p:
        rank += 120
    rank += min(pts.shape[0], 100)
    return rank


def _find_best_points(arrays: List[Tuple[str, np.ndarray]], dims: int) -> Tuple[Optional[np.ndarray], str]:
    best_rank = -9999
    best = None
    best_path = "unknown"
    for path, arr in arrays:
        rank = _rank_joint3d_candidate(path, arr) if dims == 3 else _rank_joint2d_candidate(path, arr)
        if rank > best_rank:
            pts = _sequence_points(arr, dims)
            if pts is not None:
                best_rank = rank
                best = pts
                best_path = path
    return best, best_path


def _find_vertices(arrays: List[Tuple[str, np.ndarray]]) -> Tuple[Optional[np.ndarray], str]:
    best = None
    best_path = "unknown"
    for path, arr in arrays:
        if _name_has(path, VERTEX_NAME_HINTS) or (arr.ndim >= 2 and max(arr.shape) > 1000):
            verts = _sequence_vertices(arr)
            if verts is not None:
                if best is None or verts.shape[0] * verts.shape[1] > best.shape[0] * best.shape[1]:
                    best = verts
                    best_path = path
    return best, best_path




def _pick_vertices_band(v: np.ndarray, y_norm: np.ndarray, lo: float, hi: float, side: str = "center") -> np.ndarray:
    """Pick one anatomical proxy point from an SMPL vertex cloud.

    This is a fallback when the PKL contains only SMPL vertices and no licensed
    SMPL joint regressor. It returns sparse pose landmarks, never the mesh outline.
    The points are still calculated from SMPL vertex coordinates.
    """
    mask = np.isfinite(v).all(axis=1) & (y_norm >= lo) & (y_norm <= hi)
    if mask.sum() < 8:
        # Widen the band if too few points exist.
        mid = 0.5 * (lo + hi)
        width = max(hi - lo, 0.08)
        mask = np.isfinite(v).all(axis=1) & (y_norm >= mid - width) & (y_norm <= mid + width)
    pts = v[mask]
    if len(pts) == 0:
        pts = v[np.isfinite(v).all(axis=1)]
    if len(pts) == 0:
        return np.zeros(3, dtype=float)
    if side == "left":
        q = np.quantile(pts[:, 0], 0.18)
        sub = pts[pts[:, 0] <= q]
        if len(sub) >= 3:
            pts = sub
    elif side == "right":
        q = np.quantile(pts[:, 0], 0.82)
        sub = pts[pts[:, 0] >= q]
        if len(sub) >= 3:
            pts = sub
    elif side == "front":
        q = np.quantile(pts[:, 2], 0.82)
        sub = pts[pts[:, 2] >= q]
        if len(sub) >= 3:
            pts = sub
    return np.median(pts, axis=0).astype(float)


def _mesh_proxy_joints3d(vertices: np.ndarray) -> np.ndarray:
    """Derive a 24-joint SMPL-like sparse skeleton from SMPL mesh vertices.

    Exact SMPL joints require the SMPL J_regressor/model file. The provided PKLs
    in this project contain verts but no J_regressor. This fallback calculates
    anatomical proxy landmarks from the vertex cloud so the grader uses pose
    points rather than the 6890-vertex body outline.
    """
    verts = np.asarray(vertices, dtype=float)
    if verts.ndim != 3 or verts.shape[1] < 1000 or verts.shape[2] != 3:
        raise ValueError("Expected SMPL vertices with shape [T,6890,3]")
    out = np.zeros((verts.shape[0], 24, 3), dtype=float)
    for t in range(verts.shape[0]):
        v = verts[t]
        finite = np.isfinite(v).all(axis=1)
        vv = v[finite]
        if len(vv) < 20:
            continue
        y = vv[:, 1]
        ymin, ymax = np.percentile(y, [1, 99])
        span = max(ymax - ymin, 1e-6)
        yn = np.clip((vv[:, 1] - ymin) / span, 0, 1)
        # SMPL-24 order: pelvis, hips, spine, knees, ankles, feet, neck/collars/head, shoulders/elbows/wrists/hands.
        specs = [
            (0.45,0.57,'center'), (0.42,0.55,'left'),  (0.42,0.55,'right'), (0.56,0.64,'center'),
            (0.24,0.39,'left'),   (0.24,0.39,'right'), (0.64,0.72,'center'), (0.05,0.18,'left'),
            (0.05,0.18,'right'),  (0.72,0.79,'center'), (0.00,0.10,'left'),  (0.00,0.10,'right'),
            (0.80,0.88,'center'), (0.76,0.86,'left'),  (0.76,0.86,'right'), (0.90,1.00,'center'),
            (0.72,0.85,'left'),   (0.72,0.85,'right'), (0.55,0.74,'left'),  (0.55,0.74,'right'),
            (0.38,0.62,'left'),   (0.38,0.62,'right'), (0.32,0.58,'left'),  (0.32,0.58,'right'),
        ]
        for j, (lo, hi, side) in enumerate(specs):
            out[t, j] = _pick_vertices_band(vv, yn, lo, hi, side)
    return out

def _find_regressor(arrays: List[Tuple[str, np.ndarray]], num_vertices: int) -> Optional[np.ndarray]:
    for path, arr in arrays:
        if not _name_has(path, REGRESSOR_NAME_HINTS):
            continue
        a = np.asarray(arr, dtype=float)
        if a.ndim != 2:
            continue
        if a.shape[1] == num_vertices:
            return a
        if a.shape[0] == num_vertices:
            return a.T
    return None



_EXTERNAL_J_REGRESSOR_CACHE: Dict[str, Optional[np.ndarray]] = {}

def _patch_legacy_smpl_pickle_runtime() -> None:
    """Patch Python 3.11/NumPy 1.24+ incompatibilities before loading old SMPL PKLs.

    Official legacy SMPL model PKLs may import chumpy, which expects removed
    aliases such as inspect.getargspec and np.unicode. This patch is local and
    safe for loading the model file so we can read J_regressor.
    """
    try:
        import inspect as _inspect
        if not hasattr(_inspect, "getargspec"):
            _inspect.getargspec = _inspect.getfullargspec  # type: ignore[attr-defined]
    except Exception:
        pass
    legacy_aliases = {
        "bool": bool,
        "int": int,
        "float": float,
        "complex": complex,
        "object": object,
        "str": str,
        "unicode": str,
    }
    for name, value in legacy_aliases.items():
        try:
            if not hasattr(np, name):
                setattr(np, name, value)
        except Exception:
            pass


def _as_dense_regressor(reg: Any, num_vertices: int) -> Optional[np.ndarray]:
    """Return a dense [J,V] joint regressor compatible with vertices [T,V,3]."""
    if reg is None:
        return None
    try:
        if hasattr(reg, "toarray"):
            arr = reg.toarray()
        else:
            arr = np.asarray(reg)
        arr = np.asarray(arr, dtype=float)
    except Exception:
        return None
    if arr.ndim != 2:
        return None
    if arr.shape[1] == num_vertices:
        return arr
    if arr.shape[0] == num_vertices:
        return arr.T
    return None


def _load_external_j_regressor(num_vertices: int) -> Optional[np.ndarray]:
    """Load J_regressor from a local licensed SMPL model or a standalone regressor.

    Supported environment variables:
      SMPL_MODEL_FILE=E:\\SMPL_models\\SMPL_NEUTRAL.pkl
      SMPL_REGRESSOR_FILE=E:\\SMPL_models\\J_regressor.npy/.pkl

    The model file is not distributed with this project; keep it locally.
    """
    candidates = []
    for env_name in ("SMPL_REGRESSOR_FILE", "SMPL_MODEL_FILE"):
        val = os.environ.get(env_name)
        if val:
            candidates.append((env_name, val))
    # Convenient local defaults; ignored if missing.
    for default_path in (
        r"E:\SMPL_models\SMPL_NEUTRAL.pkl",
        r"E:\SMPL_models\basicModel_neutral_lbs_10_207_0_v1.0.0.pkl",
        r"E:\SMPL_models\basicmodel_neutral_lbs_10_207_0_v1.1.0.pkl",
    ):
        candidates.append(("default", default_path))

    for source, raw_path in candidates:
        path = os.path.abspath(os.path.expanduser(raw_path))
        cache_key = f"{path}|{num_vertices}"
        if cache_key in _EXTERNAL_J_REGRESSOR_CACHE:
            return _EXTERNAL_J_REGRESSOR_CACHE[cache_key]
        if not os.path.exists(path):
            _EXTERNAL_J_REGRESSOR_CACHE[cache_key] = None
            continue
        try:
            if path.lower().endswith(".npy"):
                reg_obj = np.load(path, allow_pickle=True)
            elif path.lower().endswith(".npz"):
                data = np.load(path, allow_pickle=True)
                reg_obj = data["J_regressor"] if "J_regressor" in data else data[list(data.keys())[0]]
            else:
                _patch_legacy_smpl_pickle_runtime()
                with open(path, "rb") as f:
                    data = pickle.load(f, encoding="latin1")
                if isinstance(data, dict):
                    # Do not use `a or b` here: scipy sparse matrices and numpy arrays
                    # have ambiguous truth values. Check keys explicitly.
                    reg_obj = None
                    for key in ("J_regressor", "j_regressor", "J"):
                        if key in data and data[key] is not None:
                            reg_obj = data[key]
                            break
                else:
                    reg_obj = getattr(data, "J_regressor", None)
            reg = _as_dense_regressor(reg_obj, num_vertices)
            if reg is not None:
                print(f"Loaded external SMPL J_regressor from {path}: shape={reg.shape}", file=sys.stderr)
                _EXTERNAL_J_REGRESSOR_CACHE[cache_key] = reg
                return reg
            print(f"Warning: {path} exists but no compatible J_regressor for {num_vertices} vertices was found.", file=sys.stderr)
        except Exception as exc:
            print(f"Warning: failed to load external SMPL J_regressor from {path}: {exc}", file=sys.stderr)
        _EXTERNAL_J_REGRESSOR_CACHE[cache_key] = None
    return None

def _find_camera(arrays: List[Tuple[str, np.ndarray]], num_frames: int) -> Optional[np.ndarray]:
    best = None
    best_rank = -9999
    for path, arr in arrays:
        if not _name_has(path, CAMERA_NAME_HINTS):
            continue
        cam = _sequence_camera(arr)
        if cam is None:
            continue
        rank = 1000 if "pred_cam" in path.lower() else 500
        if cam.shape[0] == num_frames:
            rank += 100
        if rank > best_rank:
            best = cam
            best_rank = rank
    return best


def _find_bbox(arrays: List[Tuple[str, np.ndarray]], num_frames: int) -> Optional[np.ndarray]:
    best = None
    best_rank = -9999
    for path, arr in arrays:
        if not _name_has(path, BBOX_NAME_HINTS):
            continue
        bb = _sequence_bbox(arr)
        if bb is None:
            continue
        rank = 800
        if bb.shape[0] == num_frames:
            rank += 100
        if rank > best_rank:
            best = bb
            best_rank = rank
    return best


def _find_center(arrays: List[Tuple[str, np.ndarray]], num_frames: int) -> Optional[np.ndarray]:
    best = None
    best_rank = -9999
    for path, arr in arrays:
        if not _name_has(path, CENTER_NAME_HINTS):
            continue
        cen = _sequence_center(arr)
        if cen is None:
            continue
        rank = 800
        if cen.shape[0] == num_frames:
            rank += 100
        if rank > best_rank:
            best = cen
            best_rank = rank
    return best


def _find_scale(arrays: List[Tuple[str, np.ndarray]], num_frames: int) -> Optional[np.ndarray]:
    best = None
    best_rank = -9999
    for path, arr in arrays:
        if not _name_has(path, SCALE_NAME_HINTS):
            continue
        sc = _sequence_scale(arr)
        if sc is None:
            continue
        rank = 800
        if len(sc) == num_frames:
            rank += 100
        if rank > best_rank:
            best = sc
            best_rank = rank
    return best


def _find_crop_size(arrays: List[Tuple[str, np.ndarray]], num_frames: int) -> Optional[np.ndarray]:
    best = None
    best_rank = -9999
    for path, arr in arrays:
        if not _name_has(path, CROP_SIZE_NAME_HINTS):
            continue
        sc = _sequence_scale(arr)
        if sc is None:
            continue
        flat = np.asarray(sc).reshape(len(sc), -1)
        vals = flat[:, 0]
        # crop/input sizes are usually 224, 256, 384, etc.; reject body scale values around 1-3.
        if np.nanmax(vals) < 32 or np.nanmax(vals) > 2048:
            continue
        rank = 600
        if len(vals) == num_frames:
            rank += 100
        if rank > best_rank:
            best = vals.astype(float)
            best_rank = rank
    return best


def _repeat_or_trim(arr: Optional[np.ndarray], target_len: int) -> Optional[np.ndarray]:
    if arr is None:
        return None
    if len(arr) == target_len:
        return arr
    if len(arr) == 1 and target_len > 1:
        return np.repeat(arr, target_len, axis=0)
    return arr[:min(len(arr), target_len)]


def _try_optional_smplx_forward(obj: Any, arrays: List[Tuple[str, np.ndarray]]) -> Optional[np.ndarray]:
    """Optional fallback: compute joints from SMPL parameters if smplx + model files are installed.

    This intentionally does not ship SMPL model files; set SMPL_MODEL_PATH to the folder containing
    the licensed SMPL/SMPL-X model files when you need this path.
    """
    model_path = os.environ.get("SMPL_MODEL_PATH")
    if not model_path:
        return None
    try:
        import torch  # type: ignore
        import smplx  # type: ignore
    except Exception:
        return None

    data: Dict[str, np.ndarray] = {}
    for path, arr in arrays:
        low = path.lower().replace("-", "_")
        a = np.asarray(arr, dtype=float)
        base = low.split(".")[-1]
        if base in ("betas", "beta", "shape", "pred_shape", "smpl_betas") or low.endswith(".betas"):
            data["betas"] = a
        elif "global_orient" in low or "root_orient" in low:
            data["global_orient"] = a
        elif "body_pose" in low:
            data["body_pose"] = a
        elif base in ("pose", "poses", "pred_pose", "theta", "thetas", "smpl_pose", "pose_params", "full_pose"):
            # Full SMPL axis-angle pose: [global 3 | body 69].
            if a.ndim == 2 and a.shape[1] >= 72:
                data["global_orient"] = a[:, :3]
                data["body_pose"] = a[:, 3:72]
            elif a.ndim == 3 and a.shape[1] >= 24 and a.shape[2] == 3:
                data["global_orient"] = a[:, 0, :]
                data["body_pose"] = a[:, 1:24, :].reshape(a.shape[0], -1)
            elif a.ndim == 4 and a.shape[1] >= 24 and a.shape[-2:] == (3, 3):
                data["global_orient_rotmat"] = a[:, 0:1]
                data["body_pose_rotmat"] = a[:, 1:24]
        elif base in ("transl", "trans", "translation", "camera_translation", "cam_t") or "translation" in low:
            data["transl"] = a

    has_axis_angle = "global_orient" in data and "body_pose" in data
    has_rotmat = "global_orient_rotmat" in data and "body_pose_rotmat" in data
    if not has_axis_angle and not has_rotmat:
        return None

    if "global_orient" in data:
        t = data["global_orient"].shape[0]
    else:
        t = data["global_orient_rotmat"].shape[0]
    betas = data.get("betas", np.zeros((t, 10), dtype=float))
    if betas.ndim == 1:
        betas = np.repeat(betas[None, :], t, axis=0)
    if betas.shape[0] == 1 and t > 1:
        betas = np.repeat(betas, t, axis=0)
    transl = data.get("transl")
    if transl is not None and transl.ndim == 1:
        transl = np.repeat(transl[None, :], t, axis=0)

    try:
        model_type = os.environ.get("SMPL_MODEL_TYPE", "smpl")
        gender = os.environ.get("SMPL_GENDER", "neutral")
        model = smplx.create(model_path, model_type=model_type, gender=gender, batch_size=t)
        kwargs = {
            "betas": torch.tensor(betas[:, :10], dtype=torch.float32),
        }
        if "global_orient" in data:
            kwargs["global_orient"] = torch.tensor(data["global_orient"], dtype=torch.float32)
            kwargs["body_pose"] = torch.tensor(data["body_pose"], dtype=torch.float32)
        else:
            kwargs["global_orient"] = torch.tensor(data["global_orient_rotmat"], dtype=torch.float32)
            kwargs["body_pose"] = torch.tensor(data["body_pose_rotmat"], dtype=torch.float32)
            kwargs["pose2rot"] = False
        if transl is not None and transl.shape[-1] >= 3:
            kwargs["transl"] = torch.tensor(transl[:, :3], dtype=torch.float32)
        with torch.no_grad():
            output = model(**kwargs)
        return output.joints.detach().cpu().numpy().astype(float)
    except Exception as exc:
        eprint(f"Warning: SMPL_MODEL_PATH was set, but SMPL forward failed: {exc}")
        return None




def _axis_angle_to_rotmat(vec: np.ndarray) -> np.ndarray:
    """Rodrigues formula for one axis-angle vector."""
    v = np.asarray(vec, dtype=float).reshape(3)
    angle = float(np.linalg.norm(v))
    if not np.isfinite(angle) or angle < 1e-8:
        return np.eye(3, dtype=float)
    axis = v / angle
    x, y, z = axis
    K = np.array([[0, -z, y], [z, 0, -x], [-y, x, 0]], dtype=float)
    return np.eye(3) + math.sin(angle) * K + (1.0 - math.cos(angle)) * (K @ K)


def _find_smpl_axis_angle_pose(arrays: List[Tuple[str, np.ndarray]]) -> Tuple[Optional[np.ndarray], str]:
    """Find full SMPL axis-angle pose [T,24,3] without treating it as joints."""
    best = None
    best_path = "unknown"
    best_rank = -1
    global_orient = None
    body_pose = None
    for path, arr in arrays:
        low = path.lower().replace('-', '_')
        a = np.asarray(arr, dtype=float)
        base = low.split('.')[-1]
        rank = -1
        candidate = None
        if base in ("pose", "poses", "pred_pose", "theta", "thetas", "smpl_pose", "pose_params", "full_pose"):
            if a.ndim == 2 and a.shape[1] >= 72:
                candidate = a[:, :72].reshape(a.shape[0], 24, 3)
                rank = 1000
            elif a.ndim == 3 and a.shape[1] >= 24 and a.shape[2] == 3:
                candidate = a[:, :24, :]
                rank = 900
        elif "global_orient" in low or "root_orient" in low:
            if a.ndim == 2 and a.shape[1] >= 3:
                global_orient = a[:, :3]
            elif a.ndim == 3 and a.shape[-1] == 3:
                global_orient = a.reshape(a.shape[0], -1, 3)[:, 0, :]
        elif "body_pose" in low:
            if a.ndim == 2 and a.shape[1] >= 69:
                body_pose = a[:, :69].reshape(a.shape[0], 23, 3)
            elif a.ndim == 3 and a.shape[1] >= 23 and a.shape[2] == 3:
                body_pose = a[:, :23, :]
        if candidate is not None and rank > best_rank:
            best, best_path, best_rank = candidate, path, rank
    if best is None and global_orient is not None and body_pose is not None:
        t = min(len(global_orient), len(body_pose))
        best = np.concatenate([global_orient[:t, None, :], body_pose[:t, :23, :]], axis=1)
        best_path = "global_orient + body_pose"
    return best, best_path


def _try_approx_smpl_fk(arrays: List[Tuple[str, np.ndarray]]) -> Tuple[Optional[np.ndarray], str]:
    """Approximate SMPL joint coordinates from SMPL axis-angle pose.

    Exact SMPL joints require the SMPL model file because the rest joints depend on
    the learned template, shape blend shapes, and joint regressor. However, many
    student datasets only contain pred_pose/pred_shape/pred_cam and no licensed
    SMPL model file. This fallback performs simple forward kinematics with a
    fixed SMPL-24 rest skeleton. It is much better than the old bug of drawing
    rotation vectors directly as joints, and it produces a clean pose skeleton for
    the professor-facing report. For exact coordinates, set SMPL_MODEL_PATH.
    """
    pose, source = _find_smpl_axis_angle_pose(arrays)
    if pose is None:
        return None, "unknown"
    pose = np.asarray(pose, dtype=float)
    if pose.ndim != 3 or pose.shape[1] < 24 or pose.shape[2] != 3:
        return None, "unknown"
    pose = pose[:, :24, :]
    T = pose.shape[0]
    parents = np.array([-1,0,0,0,1,2,3,4,5,6,7,8,9,9,9,12,13,14,16,17,18,19,20,21], dtype=int)
    # Approximate rest offsets in meters, SMPL-24 order. y is up, x is left/right, z is forward.
    offsets = np.array([
        [0.00, 0.00, 0.00],   # pelvis
        [-0.10,-0.10, 0.00],  # l hip
        [ 0.10,-0.10, 0.00],  # r hip
        [ 0.00, 0.12, 0.00],  # spine1
        [ 0.00,-0.42, 0.02],  # l knee
        [ 0.00,-0.42, 0.02],  # r knee
        [ 0.00, 0.16, 0.00],  # spine2
        [ 0.00,-0.42, 0.00],  # l ankle
        [ 0.00,-0.42, 0.00],  # r ankle
        [ 0.00, 0.16, 0.00],  # spine3
        [ 0.00,-0.08, 0.13],  # l foot
        [ 0.00,-0.08, 0.13],  # r foot
        [ 0.00, 0.16, 0.00],  # neck
        [-0.08, 0.05, 0.00],  # l collar
        [ 0.08, 0.05, 0.00],  # r collar
        [ 0.00, 0.18, 0.00],  # head
        [-0.16, 0.00, 0.00],  # l shoulder
        [ 0.16, 0.00, 0.00],  # r shoulder
        [-0.28, 0.00, 0.00],  # l elbow
        [ 0.28, 0.00, 0.00],  # r elbow
        [-0.25, 0.00, 0.00],  # l wrist
        [ 0.25, 0.00, 0.00],  # r wrist
        [-0.08, 0.00, 0.00],  # l hand
        [ 0.08, 0.00, 0.00],  # r hand
    ], dtype=float)
    joints = np.zeros((T, 24, 3), dtype=float)
    global_R = np.zeros((T, 24, 3, 3), dtype=float)
    for t in range(T):
        local_R = np.stack([_axis_angle_to_rotmat(pose[t, j]) for j in range(24)], axis=0)
        for j in range(24):
            parent = parents[j]
            if parent < 0:
                global_R[t, j] = local_R[j]
                joints[t, j] = offsets[j]
            else:
                global_R[t, j] = global_R[t, parent] @ local_R[j]
                joints[t, j] = joints[t, parent] + global_R[t, parent] @ offsets[j]
        # Root-center so translation/camera does not pollute MPJPE.
        joints[t] -= joints[t, 0:1]
    return joints, f"approximate SMPL-24 FK from {source}; exact mode needs SMPL_MODEL_PATH"

def extract_pose_data(obj: Any) -> PoseData:
    arrays = _collect_arrays(obj)

    joints3d, joints3d_path = _find_best_points(arrays, 3)
    vertices, vertices_path = _find_vertices(arrays)

    # If direct 3D joints do not exist, compute joints from SMPL vertices.
    if joints3d is None and vertices is not None:
        reg = _find_regressor(arrays, vertices.shape[1])
        reg_source = "PKL"
        if reg is None:
            reg = _load_external_j_regressor(vertices.shape[1])
            reg_source = os.environ.get("SMPL_MODEL_FILE") or os.environ.get("SMPL_REGRESSOR_FILE") or "external/default SMPL model"
        if reg is not None:
            joints3d = np.einsum("jv,tvc->tjc", reg, vertices).astype(float)
            joints3d_path = f"SMPL joints = J_regressor @ {vertices_path} ({reg_source})"
        else:
            # Last fallback only: no official J_regressor was available. Build sparse
            # anatomical proxy joints from the mesh instead of drawing the 6890-vertex outline.
            joints3d = _mesh_proxy_joints3d(vertices)
            joints3d_path = f"SMPL mesh-derived 24 proxy joints from {vertices_path} (no J_regressor found; set SMPL_MODEL_FILE)"

    # Optional exact fallback from SMPL parameters using smplx if model files are available.
    if joints3d is None:
        joints3d = _try_optional_smplx_forward(obj, arrays)
        if joints3d is not None:
            joints3d_path = "SMPL joints generated with smplx"

    # Last-resort approximate fallback from SMPL axis-angle rotations. This is used only
    # when the PKL has pose rotations but no joints/vertices/regressor/model files.
    # It prevents the old wrong behavior: using pred_pose itself as xyz joints.
    if joints3d is None:
        joints3d, joints3d_path = _try_approx_smpl_fk(arrays)

    if joints3d is None:
        candidate_report = []
        for path, arr in arrays[:30]:
            candidate_report.append(f"{path}: shape={getattr(arr, 'shape', None)}")
        raise ValueError(
            "Could not find valid 3D JOINT coordinates in the PKL. I intentionally refused to use "
            "SMPL pose/rotation parameters such as pred_pose/body_pose/theta as joints, because those "
            "are rotations and they create the wrong star-shaped overlay.\n\n"
            "To satisfy the professor requirement, the PKL must provide one of these:\n"
            "  1) real joints/keypoints, e.g. joints3d, pred_joints, keypoints_3d; or\n"
            "  2) SMPL vertices plus J_regressor so joints = J_regressor @ vertices; or\n"
            "  3) SMPL pose/betas plus installed SMPL model files, with SMPL_MODEL_PATH set.\n\n"
            "Arrays found in this PKL:\n"
            + "\n".join(candidate_report)
        )

    # IMPORTANT: reject accidentally selected mesh vertices. A pose skeleton should be small.
    if joints3d.shape[1] > 200:
        raise ValueError(
            f"Selected array has {joints3d.shape[1]} points, which looks like SMPL mesh vertices, not pose joints. "
            "Use SMPL joints/keypoints or a joint regressor instead."
        )

    joints2d, _ = _find_best_points(arrays, 2)
    camera = _find_camera(arrays, joints3d.shape[0])
    bbox = _find_bbox(arrays, joints3d.shape[0])
    center = _find_center(arrays, joints3d.shape[0])
    scale = _find_scale(arrays, joints3d.shape[0])
    crop_size = _find_crop_size(arrays, joints3d.shape[0])

    joints2d = _repeat_or_trim(joints2d, joints3d.shape[0])
    camera = _repeat_or_trim(camera, joints3d.shape[0])
    bbox = _repeat_or_trim(bbox, joints3d.shape[0])
    center = _repeat_or_trim(center, joints3d.shape[0])
    scale = _repeat_or_trim(scale, joints3d.shape[0])
    crop_size = _repeat_or_trim(crop_size, joints3d.shape[0])

    return PoseData(
        joints3d=joints3d.astype(float),
        joints2d=joints2d, camera=camera, bbox=bbox, center=center, scale=scale, crop_size=crop_size,
        source=joints3d_path,
    )


def extract_pose_array(obj: Any) -> np.ndarray:
    # Backward-compatible helper used by any old code/tests.
    return extract_pose_data(obj).joints3d


def load_pose_pkl(path: str) -> PoseData:
    obj = load_pickle(path)
    data = extract_pose_data(obj)
    if data.joints3d.shape[2] != 3:
        data.joints3d = data.joints3d[:, :, :3]
    meta = []
    if data.joints2d is not None: meta.append(f"joints2d={data.joints2d.shape}")
    if data.camera is not None: meta.append(f"camera={data.camera.shape}")
    if data.bbox is not None: meta.append(f"bbox={data.bbox.shape}")
    if data.center is not None: meta.append(f"center={data.center.shape}")
    if data.scale is not None: meta.append(f"scale={np.asarray(data.scale).shape}")
    safe_generated_source = data.source.startswith("SMPL joints generated") or data.source.startswith("approximate SMPL-24 FK") or data.source.startswith("SMPL joints regressed")
    if (not safe_generated_source) and _looks_like_rotation_pose(data.source, data.joints3d):
        raise ValueError(f"Internal safety check failed: selected rotation-pose field as joints: {data.source}")
    eprint(f"Loaded {path}: joints3d={data.joints3d.shape}, source={data.source}" + ("; " + ", ".join(meta) if meta else ""))
    return data

# -----------------------------
# Find files
# -----------------------------
def _empty_side_map() -> Dict[str, Optional[str]]:
    return {"left": None, "right": None, "single": None}


def _assign_side_files(pool: List[str], kind: str) -> Dict[str, Optional[str]]:
    """Assign files to left/right when possible; support single-video submissions."""
    result = _empty_side_map()
    pool = sorted(pool)
    if not pool:
        return result

    # Exact side-name matching first.
    left_matches = [p for p in pool if is_left_name(os.path.basename(p))]
    right_matches = [p for p in pool if is_right_name(os.path.basename(p))]
    if left_matches:
        result["left"] = sorted(left_matches)[0]
    if right_matches:
        result["right"] = sorted(right_matches)[0]

    # Professor requirement: one video + one PKL must still be graded.
    if len(pool) == 1:
        if result["left"] is None and result["right"] is None:
            result["single"] = pool[0]
        elif result["left"] is not None and result["right"] is None:
            # Keep side label if the filename says left, but later scoring averages over available sides only.
            pass
        elif result["right"] is not None and result["left"] is None:
            pass
        return result

    # Fallback for two unnamed files: first = left, second = right, old behavior preserved.
    if result["left"] is None and result["right"] is None and len(pool) >= 2:
        result["left"] = pool[0]
        result["right"] = pool[1]
        return result

    # If one side was detected and another unnamed file remains, use it as the other side.
    used = {v for v in result.values() if v is not None}
    remaining = [p for p in pool if p not in used]
    if result["left"] is None and remaining:
        result["left"] = remaining.pop(0)
    if result["right"] is None and remaining:
        result["right"] = remaining.pop(0)
    return result


def find_side_files(folder: str) -> Dict[str, Dict[str, Optional[str]]]:
    all_files = []
    for root, _, files in os.walk(folder):
        for f in files:
            all_files.append(os.path.join(root, f))

    pkl_files = [p for p in all_files if Path(p).suffix.lower() in PKL_EXTS]
    video_files = [p for p in all_files if Path(p).suffix.lower() in IMAGE_EXTS]
    txt_files = [p for p in all_files if Path(p).suffix.lower() in TXT_EXTS]
    calib_files = [p for p in txt_files if "calib" in os.path.basename(p).lower()]

    return {
        "pkl": _assign_side_files(pkl_files, "pkl"),
        "video": _assign_side_files(video_files, "video"),
        "calib": _assign_side_files(calib_files, "calib"),
    }


def available_eval_sides(ref_files: Dict[str, Dict[str, Optional[str]]], stu_files: Dict[str, Dict[str, Optional[str]]]) -> List[str]:
    sides = []
    for side in ("left", "right"):
        if ref_files["pkl"].get(side) and stu_files["pkl"].get(side):
            sides.append(side)

    # If there is no left/right pair, process one unnamed pair.
    if not sides and ref_files["pkl"].get("single") and stu_files["pkl"].get("single"):
        sides.append("single")

    # If only one explicit side exists, that is valid too; the final average is over this one side.
    return sides


def side_display_name(side: str) -> str:
    if side == "left":
        return "Left"
    if side == "right":
        return "Right"
    return "Single"


def side_display_name_vi(side: str) -> str:
    if side == "left":
        return "Trái"
    if side == "right":
        return "Phải"
    return "Một video"

# -----------------------------
# Metrics and DTW
# -----------------------------
def _common_joints(a: np.ndarray, b: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    j = min(a.shape[0], b.shape[0])
    a = a[:j]
    b = b[:j]
    valid = np.isfinite(a).all(axis=1) & np.isfinite(b).all(axis=1)
    if valid.sum() == 0:
        return a[:0], b[:0]
    return a[valid], b[valid]

def mpjpe_frame_and_joint_errors(ref: np.ndarray, stu: np.ndarray) -> Tuple[float, np.ndarray]:
    ref, stu = _common_joints(ref, stu)
    if len(ref) == 0:
        return float("inf"), np.array([])
    if ROOT_CENTER_MPJPE and len(ref) > 0:
        ref = ref - ref[0:1]
        stu = stu - stu[0:1]
    joint_errors = np.linalg.norm(ref - stu, axis=1)
    return float(np.mean(joint_errors)), joint_errors

def pa_align(ref: np.ndarray, stu: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    ref, stu = _common_joints(ref, stu)
    if len(ref) < 3:
        return ref, stu
    mu_ref = ref.mean(axis=0, keepdims=True)
    mu_stu = stu.mean(axis=0, keepdims=True)
    x = ref - mu_ref
    y = stu - mu_stu
    norm_x = np.sqrt(np.sum(x * x))
    norm_y = np.sqrt(np.sum(y * y))
    if norm_x < 1e-12 or norm_y < 1e-12:
        return ref, stu
    x_norm = x / norm_x
    y_norm = y / norm_y
    h = y_norm.T @ x_norm
    u, _, vt = np.linalg.svd(h)
    r = u @ vt
    if np.linalg.det(r) < 0:
        vt[-1, :] *= -1
        r = u @ vt
    y_aligned = (y_norm @ r) * norm_x + mu_ref
    return ref, y_aligned

def pa_mpjpe_frame_and_joint_errors(ref: np.ndarray, stu: np.ndarray) -> Tuple[float, np.ndarray]:
    ref2, stu2 = pa_align(ref, stu)
    if len(ref2) == 0:
        return float("inf"), np.array([])
    joint_errors = np.linalg.norm(ref2 - stu2, axis=1)
    return float(np.mean(joint_errors)), joint_errors

def frame_distance(ref: np.ndarray, stu: np.ndarray, metric: str) -> float:
    if metric.upper() == "MPJPE":
        return mpjpe_frame_and_joint_errors(ref, stu)[0]
    if metric.upper() == "PA-MPJPE":
        return pa_mpjpe_frame_and_joint_errors(ref, stu)[0]
    raise ValueError("Metric must be MPJPE or PA-MPJPE")

def frame_distance_with_joints(ref: np.ndarray, stu: np.ndarray, metric: str) -> Tuple[float, np.ndarray]:
    if metric.upper() == "MPJPE":
        return mpjpe_frame_and_joint_errors(ref, stu)
    if metric.upper() == "PA-MPJPE":
        return pa_mpjpe_frame_and_joint_errors(ref, stu)
    raise ValueError("Metric must be MPJPE or PA-MPJPE")

def _dtw_j_range(i: int, n: int, m: int, radius: int) -> Tuple[int, int]:
    """Return the allowed student-index range for ref index i in a diagonal band."""
    if radius <= 0:
        return 1, m
    if n <= 1:
        center = 1
    else:
        center = int(round(1 + (i - 1) * (m - 1) / max(n - 1, 1)))
    j0 = max(1, center - radius)
    j1 = min(m, center + radius)
    return j0, j1


def _mpjpe_row_distances(ref_frame: np.ndarray, stu_block: np.ndarray) -> np.ndarray:
    """Fast MPJPE distances from one reference frame to a block of student frames."""
    if stu_block is None or len(stu_block) == 0:
        return np.array([], dtype=float)
    jcnt = min(ref_frame.shape[0], stu_block.shape[1])
    if jcnt <= 0:
        return np.full((len(stu_block),), np.inf, dtype=float)
    ref = ref_frame[:jcnt].astype(float, copy=False)
    stu = stu_block[:, :jcnt, :].astype(float, copy=False)
    if ROOT_CENTER_MPJPE and jcnt > 0:
        ref = ref - ref[0:1]
        stu = stu - stu[:, 0:1, :]
    diff = stu - ref[None, :, :]
    valid = np.isfinite(diff).all(axis=2)
    d = np.linalg.norm(diff, axis=2)
    d = np.where(valid, d, 0.0)
    counts = valid.sum(axis=1)
    sums = d.sum(axis=1)
    out = np.full((len(stu_block),), np.inf, dtype=float)
    ok = counts > 0
    out[ok] = sums[ok] / counts[ok]
    return out


def dtw_align(ref_seq: np.ndarray, stu_seq: np.ndarray, metric: str) -> Tuple[List[Tuple[int, int]], List[float]]:
    """Align reference and student sequences in time only.

    DTW returns pairs of indices: (reference_frame, student_frame). The DTW
    result is used to select matching frames, not to transform a reference pose
    onto a student image. The HTML report therefore shows the two matched frames
    side by side.
    """
    n = len(ref_seq)
    m = len(stu_seq)
    if n == 0 or m == 0:
        return [], []

    cost_metric = DTW_COST_METRIC if DTW_COST_METRIC else metric.upper()

    # Sakoe-Chiba style window around the diagonal from (1,1) to (n,m).
    # The +abs(n-m) is NOT needed because the center follows the diagonal for
    # unequal lengths.  The endpoints are always included by the diagonal center.
    if DTW_WINDOW_RATIO > 0:
        radius = max(8, int(round(max(n, m) * DTW_WINDOW_RATIO)))
    else:
        radius = 0

    cost = np.full((n + 1, m + 1), np.inf, dtype=float)
    cost[0, 0] = 0.0
    parent = np.full((n + 1, m + 1, 2), -1, dtype=int)
    dist_cache = np.full((n, m), np.nan, dtype=float)

    for i in range(1, n + 1):
        j0, j1 = _dtw_j_range(i, n, m, radius)
        if cost_metric == "MPJPE":
            row_dists = _mpjpe_row_distances(ref_seq[i - 1], stu_seq[j0 - 1:j1])
        else:
            row_dists = None
        for offset, j in enumerate(range(j0, j1 + 1)):
            if row_dists is not None:
                d = float(row_dists[offset])
            else:
                d = frame_distance(ref_seq[i - 1], stu_seq[j - 1], cost_metric)
            dist_cache[i - 1, j - 1] = d
            choices = [cost[i - 1, j], cost[i, j - 1], cost[i - 1, j - 1]]
            arg = int(np.argmin(choices))
            best_prev = choices[arg]
            if not np.isfinite(best_prev):
                continue
            if arg == 0:
                pi, pj = i - 1, j
            elif arg == 1:
                pi, pj = i, j - 1
            else:
                pi, pj = i - 1, j - 1
            cost[i, j] = d + best_prev
            parent[i, j] = [pi, pj]

    # If an aggressive window somehow blocks the final cell, fall back once to
    # full DTW so the program still produces a report.
    if not np.isfinite(cost[n, m]) and radius > 0:
        old_ratio = globals().get('DTW_WINDOW_RATIO', 0.0)
        globals()['DTW_WINDOW_RATIO'] = 0.0
        try:
            return dtw_align(ref_seq, stu_seq, metric)
        finally:
            globals()['DTW_WINDOW_RATIO'] = old_ratio

    path: List[Tuple[int, int]] = []
    i, j = n, m
    while i > 0 or j > 0:
        pi, pj = parent[i, j]
        if pi == -1 and pj == -1:
            break
        if i > 0 and j > 0:
            path.append((i - 1, j - 1))
        i, j = int(pi), int(pj)
    path.reverse()

    # Reduce to one matched reference frame per student frame by keeping the
    # lowest-cost pair for each student frame.
    best_for_student: Dict[int, Tuple[int, float]] = {}
    for ri, sj in path:
        d = dist_cache[ri, sj]
        if not np.isfinite(d):
            d = frame_distance(ref_seq[ri], stu_seq[sj], cost_metric)
        if sj not in best_for_student or d < best_for_student[sj][1]:
            best_for_student[sj] = (ri, float(d))

    reduced_path = [(best_for_student[sj][0], sj) for sj in sorted(best_for_student)]
    reduced_dist = [best_for_student[sj][1] for sj in sorted(best_for_student)]
    return reduced_path, reduced_dist

# -----------------------------
# Error grouping
# -----------------------------
def group_error_segments(frame_errors: List[Tuple[int, float]]) -> List[Tuple[int, int, float, float]]:
    """
    Input: list of (student_frame_id, avg_error) for failing frames.
    Output: list of (start_frame, end_frame, mean_error, max_error) grouped contiguously.
    """
    if not frame_errors:
        return []
    segs = []
    cur_frames = [frame_errors[0][0]]
    cur_errs = [frame_errors[0][1]]

    for frame_id, err in frame_errors[1:]:
        if frame_id == cur_frames[-1] + 1:
            cur_frames.append(frame_id)
            cur_errs.append(err)
        else:
            segs.append((cur_frames[0], cur_frames[-1], float(np.mean(cur_errs)), float(np.max(cur_errs))))
            cur_frames = [frame_id]
            cur_errs = [err]
    segs.append((cur_frames[0], cur_frames[-1], float(np.mean(cur_errs)), float(np.max(cur_errs))))
    return segs

# -----------------------------
# Calibration and drawing
# -----------------------------
def load_calib(path: Optional[str]) -> Optional[Tuple[float, float, float, float]]:
    if not path or not os.path.exists(path):
        return None
    try:
        text = Path(path).read_text(encoding="utf-8", errors="ignore").strip()
        nums = [float(x) for x in text.replace(",", " ").split() if x.strip()]
        if len(nums) >= 4:
            return nums[0], nums[1], nums[2], nums[3]
    except Exception:
        return None
    return None


def _scalar_or_none(x: Any) -> Optional[float]:
    if x is None:
        return None
    try:
        a = np.asarray(x, dtype=float).reshape(-1)
        if a.size == 0 or not np.isfinite(a[0]):
            return None
        return float(a[0])
    except Exception:
        return None


def _as_full_bbox(
    bbox: Optional[np.ndarray],
    center: Optional[np.ndarray],
    scale: Optional[np.ndarray],
    img_shape: Tuple[int, int, int],
) -> Optional[np.ndarray]:
    """Return bbox as [x1,y1,x2,y2] in full-image pixels when possible."""
    h, w = img_shape[:2]
    if bbox is not None:
        b = np.asarray(bbox, dtype=float).reshape(-1)
        if b.size >= 4 and np.isfinite(b[:4]).all():
            x1, y1, a, b4 = b[:4]
            # normalized bbox
            if max(abs(x1), abs(y1), abs(a), abs(b4)) <= 2.0:
                x1, a = x1 * w, a * w
                y1, b4 = y1 * h, b4 * h
            # xyxy if the 3rd/4th values are bigger coordinates; otherwise xywh.
            if a > x1 and b4 > y1 and (a <= 1.5 * w and b4 <= 1.5 * h):
                out = np.array([x1, y1, a, b4], dtype=float)
            else:
                out = np.array([x1, y1, x1 + max(a, 1.0), y1 + max(b4, 1.0)], dtype=float)
            out[0::2] = np.clip(out[0::2], 0, w - 1)
            out[1::2] = np.clip(out[1::2], 0, h - 1)
            if out[2] - out[0] > 10 and out[3] - out[1] > 20:
                return out

    if center is not None and scale is not None:
        c = np.asarray(center, dtype=float).reshape(-1)
        sc = np.asarray(scale, dtype=float).reshape(-1)
        if c.size >= 2 and sc.size >= 1 and np.isfinite(c[:2]).all() and np.isfinite(sc).all():
            cx, cy = c[:2]
            # HMR/SPIN convention: bbox_size = scale * 200. If already in pixels, keep it.
            if sc.size == 1:
                val = float(sc[0])
                side = val * 200.0 if val <= 20 else val
                bw = bh = side
            else:
                sx, sy = float(sc[0]), float(sc[1])
                bw = sx * 200.0 if sx <= 20 else sx
                bh = sy * 200.0 if sy <= 20 else sy
            out = np.array([cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2], dtype=float)
            out[0::2] = np.clip(out[0::2], 0, w - 1)
            out[1::2] = np.clip(out[1::2], 0, h - 1)
            if out[2] - out[0] > 10 and out[3] - out[1] > 20:
                return out
    return None


def _infer_crop_size(crop_size: Optional[np.ndarray], points2d: Optional[np.ndarray] = None) -> float:
    val = _scalar_or_none(crop_size)
    if val is not None and 32 <= val <= 2048:
        return val
    if points2d is not None:
        pts = np.asarray(points2d, dtype=float)
        finite = np.isfinite(pts[..., :2]).all(axis=-1)
        if finite.any():
            mx = float(np.nanmax(pts[..., :2][finite]))
            if 220 <= mx <= 260:
                return 224.0
            if 250 <= mx <= 300:
                return 256.0
    return 224.0


def _crop_to_full(uv_crop: np.ndarray, img_shape: Tuple[int, int, int], bbox_full: Optional[np.ndarray], crop_size: float) -> Optional[np.ndarray]:
    if bbox_full is None:
        return None
    x1, y1, x2, y2 = bbox_full.astype(float)
    bw = max(x2 - x1, 1.0)
    bh = max(y2 - y1, 1.0)
    # HMR crops are usually square around the person; use separate x/y only when bbox is clearly rectangular.
    uv = np.asarray(uv_crop, dtype=float).copy()
    uv[:, 0] = x1 + uv[:, 0] / crop_size * bw
    uv[:, 1] = y1 + uv[:, 1] / crop_size * bh
    return uv


def _points_bbox(uv: np.ndarray) -> Optional[np.ndarray]:
    pts = np.asarray(uv, dtype=float)
    if pts.ndim != 2 or pts.shape[1] < 2:
        return None
    finite = np.isfinite(pts[:, :2]).all(axis=1)
    if finite.mean() < 0.5:
        return None
    good = pts[finite, :2]
    mn = good.min(axis=0)
    mx = good.max(axis=0)
    if not np.isfinite(mn).all() or not np.isfinite(mx).all():
        return None
    return np.array([mn[0], mn[1], mx[0], mx[1]], dtype=float)


def _projection_is_reasonable(uv: np.ndarray, img_shape: Tuple[int, int, int], target_bbox: Optional[np.ndarray] = None) -> bool:
    """Conservative check for drawing on a real image.

    A projection can be mathematically finite but still visually wrong when the
    PKL stores crop-space SMPL data without the original crop transform. This
    function rejects such projections, especially long spaghetti skeletons.
    """
    h, w = img_shape[:2]
    pts = np.asarray(uv, dtype=float)
    if pts.ndim != 2 or pts.shape[1] < 2 or len(pts) == 0:
        return False
    finite = np.isfinite(pts[:, :2]).all(axis=1)
    if finite.mean() < 0.7:
        return False
    inside = finite & (pts[:, 0] >= -0.03*w) & (pts[:, 0] <= 1.03*w) & (pts[:, 1] >= -0.03*h) & (pts[:, 1] <= 1.03*h)
    if inside.mean() < 0.75:
        return False
    bb = _points_bbox(pts)
    if bb is None:
        return False
    bw, bh = bb[2]-bb[0], bb[3]-bb[1]
    if bw < 8 or bh < 20:
        return False
    if bw > 0.75*w or bh > 0.85*h:
        return False
    if target_bbox is not None:
        tx1, ty1, tx2, ty2 = np.asarray(target_bbox, dtype=float)[:4]
        tw, th = max(tx2-tx1, 1.0), max(ty2-ty1, 1.0)
        tcx, tcy = (tx1+tx2)/2, (ty1+ty2)/2
        pcx, pcy = (bb[0]+bb[2])/2, (bb[1]+bb[3])/2
        if abs(pcx - tcx) > 0.45*tw or abs(pcy - tcy) > 0.45*th:
            return False
        if bw > 1.25*tw or bh > 1.25*th:
            return False
        if bh < 0.25*th:
            return False
        pad_x, pad_y = 0.20*tw, 0.15*th
        in_box = finite & (pts[:,0] >= tx1-pad_x) & (pts[:,0] <= tx2+pad_x) & (pts[:,1] >= ty1-pad_y) & (pts[:,1] <= ty2+pad_y)
        if in_box.mean() < 0.65:
            return False
    return True

def _valid_2d_points(
    points2d: Optional[np.ndarray],
    img_shape: Tuple[int, int, int],
    bbox_full: Optional[np.ndarray] = None,
    crop_size: float = 224.0,
) -> Optional[np.ndarray]:
    if points2d is None:
        return None
    pts = np.asarray(points2d, dtype=float)
    if pts.ndim != 2 or pts.shape[1] < 2 or len(pts) == 0:
        return None
    pts = pts[:, :2].copy()
    h, w = img_shape[:2]
    finite = np.isfinite(pts).all(axis=1)
    if finite.mean() < 0.5:
        return None

    good = pts[finite]
    mn = good.min(axis=0)
    mx = good.max(axis=0)
    span = mx - mn

    # [0, 1] normalized coordinates. If bbox metadata exists, treat this as crop normalized; otherwise full image.
    if mn[0] >= -0.05 and mn[1] >= -0.05 and mx[0] <= 1.05 and mx[1] <= 1.05:
        if bbox_full is not None:
            crop = np.stack([pts[:,0] * crop_size, pts[:,1] * crop_size], axis=1)
            uv = _crop_to_full(crop, img_shape, bbox_full, crop_size)
            if uv is not None and _projection_is_reasonable(uv, img_shape, bbox_full):
                return uv
        uv = pts.copy()
        uv[:, 0] *= w
        uv[:, 1] *= h
        if _projection_is_reasonable(uv, img_shape):
            return uv

    # [-1, 1] normalized coordinates.
    if mn[0] >= -1.2 and mn[1] >= -1.2 and mx[0] <= 1.2 and mx[1] <= 1.2:
        crop = np.stack([(pts[:,0] + 1.0) * 0.5 * crop_size, (pts[:,1] + 1.0) * 0.5 * crop_size], axis=1)
        if bbox_full is not None:
            uv = _crop_to_full(crop, img_shape, bbox_full, crop_size)
            if uv is not None and _projection_is_reasonable(uv, img_shape, bbox_full):
                return uv
        uv = np.stack([(pts[:,0] + 1.0) * 0.5 * w, (pts[:,1] + 1.0) * 0.5 * h], axis=1)
        if _projection_is_reasonable(uv, img_shape):
            return uv

    # Crop coordinates such as 224x224/256x256: convert with bbox metadata.
    if mx[0] <= max(320, crop_size * 1.25) and mx[1] <= max(320, crop_size * 1.25) and bbox_full is not None:
        uv = _crop_to_full(pts, img_shape, bbox_full, crop_size)
        if uv is not None and _projection_is_reasonable(uv, img_shape, bbox_full):
            return uv

    # Direct full-image pixel coordinates.
    inside = finite & (pts[:, 0] > -0.25 * w) & (pts[:, 0] < 1.25 * w) & (pts[:, 1] > -0.25 * h) & (pts[:, 1] < 1.25 * h)
    if inside.mean() >= 0.65 and span[0] > max(8, 0.01 * w) and span[1] > max(20, 0.03 * h):
        if _projection_is_reasonable(pts, img_shape, bbox_full):
            return pts
    return None


def _project_weak_perspective(points3d: np.ndarray, cam: np.ndarray, img_shape: Tuple[int, int, int], bbox_full: Optional[np.ndarray] = None, crop_size: float = 224.0) -> Optional[np.ndarray]:
    """Project HMR/SPIN-style weak-perspective camera [scale, tx, ty].

    If bbox/center/scale metadata exists, project first into the network crop
    and then map the crop back to the original frame. This is the critical fix.
    """
    if cam is None:
        return None
    c = np.asarray(cam, dtype=float).reshape(-1)
    if c.size < 3 or not np.isfinite(c[:3]).all():
        return None
    s, tx, ty = c[:3]
    if abs(s) < 1e-8 or abs(s) > 50:
        return None
    h, w = img_shape[:2]
    pts = np.asarray(points3d, dtype=float)
    candidates = []
    for ysign in (1.0, -1.0):
        x = s * pts[:, 0] + tx
        y = s * (ysign * pts[:, 1]) + ty
        if bbox_full is not None:
            crop = np.stack([(x + 1.0) * 0.5 * crop_size, (y + 1.0) * 0.5 * crop_size], axis=1)
            uv = _crop_to_full(crop, img_shape, bbox_full, crop_size)
        else:
            uv = np.stack([(x + 1.0) * 0.5 * w, (y + 1.0) * 0.5 * h], axis=1)
        if uv is not None and _projection_is_reasonable(uv, img_shape, bbox_full):
            candidates.append(uv)
    if candidates:
        return candidates[0]
    return None


def _project_with_translation_and_calib(points3d: np.ndarray, cam: Optional[np.ndarray], calib: Optional[Tuple[float, float, float, float]], img_shape: Tuple[int, int, int], bbox_full: Optional[np.ndarray] = None) -> Optional[np.ndarray]:
    if calib is None:
        return None
    pts = np.asarray(points3d, dtype=float).copy()
    if cam is not None:
        c = np.asarray(cam, dtype=float).reshape(-1)
        if c.size >= 3 and abs(c[0]) < 100 and abs(c[1]) < 100 and c[2] > 0:
            pts = pts + c[:3][None, :]
    fx, fy, cx, cy = calib
    z = pts[:, 2].copy()
    z_safe = np.where(np.abs(z) < 1e-6, 1e-6, z)
    uv = np.stack([fx * (pts[:, 0] / z_safe) + cx, fy * (-pts[:, 1] / z_safe) + cy], axis=1)
    if _projection_is_reasonable(uv, img_shape, bbox_full):
        return uv
    return None


def _estimate_person_bbox_hog(frame: Optional[np.ndarray]) -> Optional[np.ndarray]:
    if frame is None:
        return None
    try:
        h, w = frame.shape[:2]
        if h < 80 or w < 80:
            return None
        hog = cv2.HOGDescriptor()
        hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
        scale = 480.0 / max(h, w) if max(h, w) > 480 else 1.0
        small = cv2.resize(frame, (int(w*scale), int(h*scale))) if scale != 1.0 else frame
        rects, weights = hog.detectMultiScale(small, winStride=(8,8), padding=(8,8), scale=1.05)
        if len(rects) == 0:
            return None
        best = None
        best_score = -1e9
        for i, (x, y, rw, rh) in enumerate(rects):
            if scale != 1.0:
                x, y, rw, rh = x/scale, y/scale, rw/scale, rh/scale
            aspect = rh / max(rw, 1.0)
            if aspect < 1.2 or aspect > 5.5:
                continue
            area = rw * rh
            weight = float(weights[i]) if weights is not None and len(weights) > i else 0.0
            score = area + 1000 * weight
            if score > best_score:
                best_score = score
                best = np.array([x, y, x+rw, y+rh], dtype=float)
        if best is not None:
            pad_x, pad_y = 0.10 * (best[2]-best[0]), 0.08 * (best[3]-best[1])
            best = np.array([best[0]-pad_x, best[1]-pad_y, best[2]+pad_x, best[3]+pad_y], dtype=float)
            best[0::2] = np.clip(best[0::2], 0, w - 1)
            best[1::2] = np.clip(best[1::2], 0, h - 1)
            return best
    except Exception:
        return None
    return None



def _estimate_person_bbox_face(frame: Optional[np.ndarray]) -> Optional[np.ndarray]:
    """Estimate body bbox from frontal/profile face detection.

    This lightweight OpenCV-only fallback often works better than HOG for side-view videos.
    """
    if frame is None:
        return None
    try:
        h, w = frame.shape[:2]
        if h < 80 or w < 80:
            return None
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)
        cascades = []
        for fname in ("haarcascade_frontalface_default.xml", "haarcascade_profileface.xml"):
            path = os.path.join(cv2.data.haarcascades, fname)
            if os.path.exists(path):
                cas = cv2.CascadeClassifier(path)
                if not cas.empty():
                    cascades.append(cas)
        faces = []
        for cas in cascades:
            rects = cas.detectMultiScale(gray, scaleFactor=1.08, minNeighbors=3, minSize=(18,18))
            for x, y, fw, fh in rects:
                if fw > 0 and fh > 0:
                    faces.append((x, y, fw, fh))
        if not faces:
            return None
        x, y, fw, fh = max(faces, key=lambda r: r[2]*r[3])
        cx = x + fw/2.0
        bw = max(4.2*fw, 0.16*w)
        bh = max(8.5*fh, 0.45*h)
        x1 = cx - bw/2.0
        y1 = y - 1.0*fh
        x2 = cx + bw/2.0
        y2 = y1 + bh
        bb = np.array([x1, y1, x2, y2], dtype=float)
        bb[0::2] = np.clip(bb[0::2], 0, w-1)
        bb[1::2] = np.clip(bb[1::2], 0, h-1)
        if bb[2]-bb[0] > 20 and bb[3]-bb[1] > 60:
            return bb
    except Exception:
        pass
    return None


def _estimate_person_bbox_visual(frame: Optional[np.ndarray]) -> Optional[np.ndarray]:
    """Very conservative image-only person-region guess. Used only for overlay fallback."""
    if frame is None:
        return None
    try:
        h, w = frame.shape[:2]
        if h < 80 or w < 80:
            return None
        small_scale = 480.0 / max(h, w) if max(h, w) > 480 else 1.0
        img = cv2.resize(frame, (int(w*small_scale), int(h*small_scale))) if small_scale != 1.0 else frame.copy()
        sh, sw = img.shape[:2]
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        sat = hsv[:,:,1]
        val = hsv[:,:,2]
        mask = ((sat > 35) | (val < 120)).astype(np.uint8) * 255
        mask[:max(2, int(0.03*sh)), :] = 0
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5,5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
        best = None
        best_score = -1.0
        cx_img = sw / 2.0
        for i in range(1, n):
            x, y, bw, bh, area = stats[i]
            if area < 0.004*sw*sh:
                continue
            aspect = bh / max(bw, 1)
            if aspect < 1.1 or bh < 0.20*sh:
                continue
            comp_cx = x + bw/2.0
            center_bonus = 1.0 - min(abs(comp_cx - cx_img) / max(cx_img,1.0), 1.0)
            score = float(area) * (0.7 + 0.6*center_bonus) * min(aspect, 4.0)
            if score > best_score:
                best_score = score
                best = np.array([x, y, x+bw, y+bh], dtype=float)
        if best is None:
            return None
        if small_scale != 1.0:
            best = best / small_scale
        pad_x = 0.25*(best[2]-best[0])
        pad_y_top = 0.18*(best[3]-best[1])
        pad_y_bot = 0.10*(best[3]-best[1])
        bb = np.array([best[0]-pad_x, best[1]-pad_y_top, best[2]+pad_x, best[3]+pad_y_bot], dtype=float)
        bb[0::2] = np.clip(bb[0::2], 0, w-1)
        bb[1::2] = np.clip(bb[1::2], 0, h-1)
        if bb[2]-bb[0] > 20 and bb[3]-bb[1] > 60:
            return bb
    except Exception:
        pass
    return None


def _estimate_person_bbox_multi(frame: Optional[np.ndarray]) -> Optional[np.ndarray]:
    """Try several OpenCV-only person bbox estimators."""
    if frame is None:
        return None
    candidates = []
    for fn in (_estimate_person_bbox_hog, _estimate_person_bbox_face, _estimate_person_bbox_visual):
        bb = fn(frame)
        if bb is not None:
            candidates.append(np.asarray(bb, dtype=float))
    if not candidates:
        return None
    h, w = frame.shape[:2]
    best = None
    best_score = -1e18
    for idx, bb in enumerate(candidates):
        x1, y1, x2, y2 = bb
        bw, bh = max(x2-x1, 1.0), max(y2-y1, 1.0)
        aspect = bh / bw
        if aspect < 1.0 or aspect > 6.0:
            continue
        area = bw * bh
        cx = (x1+x2)/2.0
        central = 1.0 - min(abs(cx - w/2.0) / max(w/2.0,1.0), 1.0)
        score = area * (0.6 + 0.4*central) - 1000*idx
        if score > best_score:
            best_score = score
            best = bb
    return best if best is not None else candidates[0]


def _expanded_bbox(bb: np.ndarray, img_shape: Tuple[int, int, int], px: float = 0.25, py: float = 0.18) -> np.ndarray:
    h, w = img_shape[:2]
    x1,y1,x2,y2 = np.asarray(bb, dtype=float)[:4]
    bw, bh = max(x2-x1,1.0), max(y2-y1,1.0)
    out = np.array([x1-px*bw, y1-py*bh, x2+px*bw, y2+py*bh], dtype=float)
    out[0::2] = np.clip(out[0::2], 0, w-1)
    out[1::2] = np.clip(out[1::2], 0, h-1)
    return out


def _projection_has_spaghetti(uv: np.ndarray, img_shape: Tuple[int, int, int], target_bbox: Optional[np.ndarray]) -> bool:
    """Detect long, visually useless skeleton edges."""
    pts = np.asarray(uv, dtype=float)
    if pts.ndim != 2 or pts.shape[1] < 2:
        return True
    edges = skeleton_edges(len(pts))
    if not edges:
        return False
    h, w = img_shape[:2]
    if target_bbox is not None:
        tb = np.asarray(target_bbox, dtype=float)[:4]
        body_h = max(tb[3]-tb[1], 1.0)
        body_w = max(tb[2]-tb[0], 1.0)
    else:
        body_h = h
        body_w = w
    long_count = 0
    valid_count = 0
    for a,b in edges:
        if a >= len(pts) or b >= len(pts):
            continue
        pa,pb = pts[a,:2], pts[b,:2]
        if not (np.isfinite(pa).all() and np.isfinite(pb).all()):
            continue
        valid_count += 1
        d = float(np.linalg.norm(pa-pb))
        if d > 0.55*body_h or d > 1.20*body_w:
            long_count += 1
    if valid_count >= 4 and long_count / valid_count > 0.20:
        return True
    bb = _points_bbox(pts)
    if bb is not None and target_bbox is not None:
        pw, ph = bb[2]-bb[0], bb[3]-bb[1]
        tb = np.asarray(target_bbox, dtype=float)[:4]
        tw, th = tb[2]-tb[0], tb[3]-tb[1]
        if pw > 1.35*tw or ph > 1.35*th:
            return True
    return False


def _sanitize_or_fit_overlay(candidate_uv: Optional[np.ndarray], points3d: np.ndarray, img_shape: Tuple[int, int, int], target_bbox: Optional[np.ndarray]) -> np.ndarray:
    """Return candidate only if it is visually safe; otherwise fit joints into bbox."""
    if target_bbox is None:
        target_bbox = _fallback_person_bbox(img_shape)
    target_expanded = _expanded_bbox(target_bbox, img_shape, 0.15, 0.10)
    if candidate_uv is not None:
        if _projection_is_reasonable(candidate_uv, img_shape, target_expanded) and not _projection_has_spaghetti(candidate_uv, img_shape, target_expanded):
            return candidate_uv
    return _auto_fit_to_bbox(points3d, img_shape, target_bbox)

def _fallback_person_bbox(img_shape: Tuple[int, int, int]) -> np.ndarray:
    h, w = img_shape[:2]
    return np.array([0.28*w, 0.12*h, 0.72*w, 0.94*h], dtype=float)


def _auto_fit_to_bbox(points3d: np.ndarray, img_shape: Tuple[int, int, int], target_bbox: Optional[np.ndarray]) -> np.ndarray:
    """Last-resort visual overlay: fit SMPL joint configuration into person bbox.

    This does NOT affect the MPJPE score. It only prevents a useless visualization when
    the PKL lacks full-frame camera/crop metadata. The joints still come from SMPL/PKL.
    """
    pts = np.asarray(points3d, dtype=float)
    n = len(pts)
    if n == 0:
        return np.zeros((0, 2), dtype=float)
    h, w = img_shape[:2]
    bb = target_bbox.copy() if target_bbox is not None else _fallback_person_bbox(img_shape)
    x1, y1, x2, y2 = bb
    bw, bh = max(x2-x1, 1.0), max(y2-y1, 1.0)
    # Candidate planes. x/-y is common for upright SMPL; z/-y helps if the camera is from the side.
    planes = [
        np.stack([pts[:,0], -pts[:,1]], axis=1),
        np.stack([-pts[:,0], -pts[:,1]], axis=1),
        np.stack([pts[:,2], -pts[:,1]], axis=1),
        np.stack([-pts[:,2], -pts[:,1]], axis=1),
        np.stack([pts[:,0], -pts[:,2]], axis=1),
    ]
    best_uv = None
    best_score = 1e18
    target_ratio = bh / max(bw, 1.0)
    for xy in planes:
        finite = np.isfinite(xy).all(axis=1)
        if finite.mean() < 0.5:
            continue
        good = xy[finite]
        mn, mx = good.min(axis=0), good.max(axis=0)
        span = np.maximum(mx - mn, 1e-6)
        ratio = span[1] / max(span[0], 1e-6)
        score = abs(math.log(max(ratio, 1e-6) / max(target_ratio, 1e-6)))
        # Prefer upright skeletons: vertical span bigger than horizontal.
        if span[1] < span[0]:
            score += 0.5
        norm = (xy - mn) / span
        scale = 0.88 * min(bw, bh)  # uniform scale, preserve body shape
        # If skeleton aspect is very narrow, allow bbox height to dominate.
        scale = min(0.88 * bw / max(span[0]/max(span[1],1e-6), 0.2), 0.88 * bh)
        uv = np.zeros((n, 2), dtype=float)
        xy_centered = xy - (mn + mx)/2
        if span[1] >= span[0]:
            s = 0.88 * bh / span[1]
        else:
            s = 0.88 * bw / span[0]
        uv[:,0] = (x1+x2)/2 + xy_centered[:,0] * s
        uv[:,1] = (y1+y2)/2 + xy_centered[:,1] * s
        if score < best_score:
            best_score = score
            best_uv = uv
    if best_uv is None:
        best_uv = np.column_stack([np.full(n, (x1+x2)/2), np.linspace(y1, y2, n)])
    return best_uv




def _proxy_joints2d_from_cloud(uv: np.ndarray) -> Optional[np.ndarray]:
    """Derive sparse 24 SMPL-like 2D joints from a projected SMPL mesh cloud."""
    pts = np.asarray(uv, dtype=float)
    finite = np.isfinite(pts).all(axis=1)
    pts = pts[finite]
    if len(pts) < 50:
        return None
    x = pts[:, 0]
    y = pts[:, 1]
    x1, x2 = np.percentile(x, [1, 99])
    y1, y2 = np.percentile(y, [1, 99])
    if x2 - x1 < 8 or y2 - y1 < 20:
        return None
    yn = np.clip((y - y1) / max(y2 - y1, 1e-6), 0, 1)  # 0=head/top, 1=feet/bottom in image pixels

    def pick(lo, hi, side='center'):
        mask = (yn >= lo) & (yn <= hi)
        pp = pts[mask]
        if len(pp) < 6:
            mid = 0.5 * (lo + hi)
            pp = pts[(yn >= mid - 0.08) & (yn <= mid + 0.08)]
        if len(pp) == 0:
            pp = pts
        if side == 'left':
            q = np.quantile(pp[:, 0], 0.18)
            sub = pp[pp[:, 0] <= q]
            if len(sub) >= 3:
                pp = sub
        elif side == 'right':
            q = np.quantile(pp[:, 0], 0.82)
            sub = pp[pp[:, 0] >= q]
            if len(sub) >= 3:
                pp = sub
        return np.median(pp, axis=0)

    # Convert image-space bands to SMPL-24 semantic order. Since y=0 is top,
    # head bands are small numbers and feet bands are large numbers.
    specs = [
        (0.50,0.64,'center'), (0.48,0.62,'left'),  (0.48,0.62,'right'), (0.40,0.52,'center'),
        (0.68,0.82,'left'),   (0.68,0.82,'right'), (0.31,0.42,'center'), (0.86,0.98,'left'),
        (0.86,0.98,'right'),  (0.24,0.34,'center'), (0.94,1.00,'left'),  (0.94,1.00,'right'),
        (0.13,0.24,'center'), (0.18,0.30,'left'),  (0.18,0.30,'right'), (0.00,0.12,'center'),
        (0.20,0.34,'left'),   (0.20,0.34,'right'), (0.32,0.55,'left'),  (0.32,0.55,'right'),
        (0.42,0.70,'left'),   (0.42,0.70,'right'), (0.48,0.74,'left'),  (0.48,0.74,'right'),
    ]
    return np.vstack([pick(lo, hi, side) for lo, hi, side in specs]).astype(float)


def _calib_candidates_for_frame(calib: Tuple[float, float, float, float], img_shape: Tuple[int, int, int]) -> List[Tuple[str, Tuple[float, float, float, float]]]:
    """Return plausible intrinsic variants for the actual decoded frame.

    Some phone videos are stored/decoded as portrait (1080x1920), while the
    calibration file may still contain the landscape principal point (960,540).
    This function tries both the given values and a swapped cx/cy variant.  It
    does not overwrite the calibration; it only lets the projection chooser pick
    the candidate that actually lands on the person in the frame.
    """
    fx, fy, cx, cy = calib
    h, w = img_shape[:2]
    out: List[Tuple[str, Tuple[float, float, float, float]]] = []

    def add(name: str, K: Tuple[float, float, float, float]):
        rounded = tuple(round(float(x), 6) for x in K)
        if not any(tuple(round(float(y), 6) for y in old[1]) == rounded for old in out):
            out.append((name, tuple(float(x) for x in K)))

    add("given", (fx, fy, cx, cy))
    add("swap_cx_cy", (fx, fy, cy, cx))
    # If the principal point is clearly the opposite of the decoded frame center,
    # also try a direct frame-center fallback. This is a safety net for rotated
    # MOV/MP4 files where metadata rotation and calibration disagree.
    add("frame_center", (fx, fy, w / 2.0, h / 2.0))
    return out


def _score_projected_mesh_cloud(cloud: np.ndarray, img_shape: Tuple[int, int, int], target_bbox: Optional[np.ndarray]) -> float:
    h, w = img_shape[:2]
    bb = _points_bbox(cloud)
    if bb is None:
        return -1e9
    bw, bh = bb[2] - bb[0], bb[3] - bb[1]
    if bw < 20 or bh < 60 or bw > 1.25 * w or bh > 1.25 * h:
        return -1e9
    center = np.array([(bb[0] + bb[2]) / 2.0, (bb[1] + bb[3]) / 2.0])
    ratio = bh / max(bw, 1.0)

    # Human standing projections are usually taller than wide, but side views can
    # be slimmer or wider because arms/pose change the silhouette.
    score = 0.0
    score -= abs(math.log(max(ratio, 1e-6) / 2.6))
    # Favor a body-size projection, not a tiny cluster or whole-image explosion.
    score -= 0.35 * abs(math.log(max(bh, 1.0) / max(0.36 * h, 1.0)))
    score -= 0.20 * abs(math.log(max(bw, 1.0) / max(0.18 * w, 1.0)))

    # If a person box is estimated from the image, use it as a strong visual anchor.
    if target_bbox is not None:
        tx1, ty1, tx2, ty2 = target_bbox
        tbw, tbh = max(tx2 - tx1, 1.0), max(ty2 - ty1, 1.0)
        tcenter = np.array([(tx1 + tx2) / 2.0, (ty1 + ty2) / 2.0])
        score -= 1.65 * abs(center[0] - tcenter[0]) / tbw
        score -= 1.65 * abs(center[1] - tcenter[1]) / tbh
        score -= 0.55 * abs(math.log(max(bh, 1.0) / max(tbh, 1.0)))
        score -= 0.35 * abs(math.log(max(bw, 1.0) / max(tbw, 1.0)))
        # Encourage overlap with the person region.
        ix1, iy1 = max(bb[0], tx1), max(bb[1], ty1)
        ix2, iy2 = min(bb[2], tx2), min(bb[3], ty2)
        inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
        union = bw * bh + tbw * tbh - inter + 1e-6
        score += 2.5 * (inter / union)
    else:
        # Without target box, prefer being inside the frame and near the visual center.
        score -= 0.5 * abs(center[0] - w / 2.0) / w
        score -= 0.5 * abs(center[1] - h / 2.0) / h
    return score


def _project_vertices_to_sparse_2d(vertices3d: Optional[np.ndarray], calib: Optional[Tuple[float,float,float,float]], img_shape: Tuple[int,int,int], frame_image: Optional[np.ndarray] = None) -> Optional[np.ndarray]:
    """Project SMPL mesh with calibration, then derive sparse 2D pose joints.

    v8 fix: the provided calibration files are intrinsics only (fx fy cx cy).  The
    decoded videos can be portrait even when the calibration was written in
    landscape order.  In addition, the SMPL vertices in these PKLs use a local
    coordinate convention where the vertical body axis can be stored in a
    different component than the image x/y axes.  Therefore this function tries
    the small set of physically plausible axis mappings and calibration-center
    variants, then chooses the one whose projected mesh lands on the person.
    """
    if vertices3d is None or calib is None:
        return None
    v = np.asarray(vertices3d, dtype=float)
    if v.ndim != 2 or v.shape[0] < 1000 or v.shape[1] != 3:
        return None
    finite = np.isfinite(v).all(axis=1)
    v = v[finite]
    if len(v) < 100:
        return None
    h, w = img_shape[:2]
    target_bbox = _estimate_person_bbox_multi(frame_image) if frame_image is not None else None
    candidates: List[Tuple[float, np.ndarray, str]] = []

    # Common coordinate conventions observed in SMPL camera-space exports:
    # (0,1,2): X horizontal, Y vertical, Z depth.
    # (1,0,2): Y horizontal, X vertical, Z depth. This matches the uploaded sample
    #           after OpenCV decodes the phone video as portrait.
    # The remaining permutations are kept as a safety net and are penalized unless
    # they visibly land on the person.
    axis_orders = [(0,1,2), (1,0,2), (0,2,1), (1,2,0), (2,0,1), (2,1,0)]
    for kname, K in _calib_candidates_for_frame(calib, img_shape):
        fx, fy, cx, cy = K
        for perm in axis_orders:
            base = v[:, perm]
            # Depth must be positive for most vertices. Try signs because some
            # SMPL pipelines use y-up or camera-forward negative conventions.
            for signs in itertools.product((1.0, -1.0), repeat=3):
                pts = base * np.asarray(signs, dtype=float)
                X, Y, Z = pts[:, 0], pts[:, 1], pts[:, 2]
                good_z = np.isfinite(Z) & (Z > 1e-4)
                if good_z.mean() < 0.60:
                    continue
                z = np.where(np.abs(Z) < 1e-6, np.nan, Z)
                uv = np.stack([fx * (X / z) + cx, fy * (Y / z) + cy], axis=1)
                finite_uv = np.isfinite(uv).all(axis=1)
                # Allow a small margin because limbs can be near edges, but reject
                # projections that explode across the image.
                inside = finite_uv & (uv[:,0] >= -0.12*w) & (uv[:,0] <= 1.12*w) & (uv[:,1] >= -0.12*h) & (uv[:,1] <= 1.12*h)
                inside_frac = float(inside.mean())
                if inside_frac < 0.45:
                    continue
                cloud = uv[inside]
                bb = _points_bbox(cloud)
                if bb is None:
                    continue
                score = _score_projected_mesh_cloud(cloud, img_shape, target_bbox)
                if score < -1e8:
                    continue
                score += 2.0 * inside_frac
                # Slightly prefer common mappings and the frame-center/swap center
                # when they solve the portrait-video case.
                if perm == (1,0,2):
                    score += 0.25
                elif perm == (0,1,2):
                    score += 0.15
                if kname in ("swap_cx_cy", "frame_center") and h > w:
                    score += 0.15
                joints2d = _proxy_joints2d_from_cloud(cloud)
                if joints2d is None:
                    continue
                if _projection_has_spaghetti(joints2d, img_shape, target_bbox):
                    # Do not completely discard: a good projection may still have
                    # slightly noisy mesh-derived limb proxies.  Drawing later also
                    # prunes long edges.  Penalize only.
                    score -= 1.0
                candidates.append((score, joints2d, f"{kname} perm={perm} signs={signs}"))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


# -----------------------------
# MediaPipe visualization backend
# -----------------------------
_MP_POSE = None
_MP_AVAILABLE = None
_MP_WARNED = False

def _mediapipe_pose_points(frame_image: Optional[np.ndarray]) -> Optional[np.ndarray]:
    """Return 33 image-space pose landmarks from MediaPipe, or None.

    This is used only for the HTML visualization overlay. It does NOT change the
    MPJPE/PA-MPJPE score, which still comes from the PKL/SMPL data.

    Why this exists: the provided PKL files contain SMPL vertices/pose but do not
    contain full-frame 2D joints, bbox/crop metadata, or camera extrinsics. With
    intrinsics alone, exact SMPL-to-image projection is underdetermined. MediaPipe
    gives the missing image-space location so the report shows a clean skeleton
    on the actual person instead of a flying SMPL projection.
    """
    global _MP_POSE, _MP_AVAILABLE, _MP_WARNED
    if frame_image is None:
        return None
    if _MP_AVAILABLE is False:
        return None
    try:
        if _MP_POSE is None:
            import mediapipe as mp  # optional dependency
            _MP_AVAILABLE = True
            _MP_POSE = mp.solutions.pose.Pose(
                static_image_mode=True,
                model_complexity=2,
                enable_segmentation=False,
                min_detection_confidence=0.35,
            )
        rgb = cv2.cvtColor(frame_image, cv2.COLOR_BGR2RGB)
        res = _MP_POSE.process(rgb)
        if not res or not res.pose_landmarks:
            return None
        h, w = frame_image.shape[:2]
        pts = []
        visible = 0
        for lm in res.pose_landmarks.landmark:
            x = float(lm.x) * w
            y = float(lm.y) * h
            v = float(getattr(lm, 'visibility', 1.0))
            if v >= 0.25 and np.isfinite(x) and np.isfinite(y):
                visible += 1
                pts.append([x, y])
            else:
                pts.append([np.nan, np.nan])
        if visible < 8:
            return None
        return np.asarray(pts, dtype=float)
    except Exception as exc:
        _MP_AVAILABLE = False
        if not _MP_WARNED:
            print(f"MediaPipe overlay unavailable ({exc}); falling back to SMPL projection. Install compatible MediaPipe, e.g. mediapipe==0.10.21", file=sys.stderr)
            _MP_WARNED = True
        return None

def project_points(
    points3d: np.ndarray,
    calib: Optional[Tuple[float, float, float, float]],
    img_shape: Tuple[int, int, int],
    points2d: Optional[np.ndarray] = None,
    camera: Optional[np.ndarray] = None,
    bbox: Optional[np.ndarray] = None,
    center: Optional[np.ndarray] = None,
    scale: Optional[np.ndarray] = None,
    crop_size: Optional[np.ndarray] = None,
    vertices3d: Optional[np.ndarray] = None,
    frame_image: Optional[np.ndarray] = None,
) -> np.ndarray:
    """Project pose joints to original video-frame pixels.

    final behavior is intentionally conservative for professor-facing visualization:
    - MPJPE scoring still uses true 3D joints.
    - The overlay first tries real 2D/camera projection.
    - If the result does not sit on the person or contains long spaghetti edges,
      it uses the same SMPL joints but fits their 2D layout into the detected
      person bbox. This avoids drawing SMPL mesh/contour and avoids the flying
      skeleton caused by missing crop-camera metadata.
    """
    pts = np.asarray(points3d, dtype=float)
    if len(pts) == 0:
        return np.zeros((0, 2), dtype=float)

    # v9 emergency professor-facing fix: use full-frame 2D pose detection for
    # visualization when available. This prevents the wrong/flying SMPL overlay.
    # Scoring is unchanged and still uses SMPL/PKL joints.
    if VIS_BACKEND in ("mediapipe", "mp", "2d", "auto2d", "image2d"):
        mp_pts = _mediapipe_pose_points(frame_image)
        if mp_pts is not None:
            return mp_pts

    crop = _infer_crop_size(crop_size, points2d)
    meta_bbox = _as_full_bbox(bbox, center, scale, img_shape)
    visual_bbox = _estimate_person_bbox_multi(frame_image) if frame_image is not None else None
    target_bbox = meta_bbox if meta_bbox is not None else visual_bbox
    if target_bbox is None:
        target_bbox = _fallback_person_bbox(img_shape)

    mode = OVERLAY_MODE

    # v7: If SMPL vertices and calib exist, project the mesh cloud using the real
    # camera intrinsics, then draw only sparse pose joints derived from that cloud.
    # This directly addresses the professor's complaint: no SMPL outline/mesh,
    # and no blind drawing of rotation parameters.
    if mode in ("calib", "auto", "auto_safe", "projection"):
        uv_mesh = _project_vertices_to_sparse_2d(vertices3d, calib, img_shape, frame_image)
        if uv_mesh is not None:
            return uv_mesh

    if mode in ("fit", "bbox_fit", "safe_fit"):
        return _auto_fit_to_bbox(pts, img_shape, target_bbox)

    candidate = None
    uv = _valid_2d_points(points2d, img_shape, target_bbox, crop)
    if uv is not None:
        candidate = uv

    if candidate is None:
        uv = _project_weak_perspective(pts, camera, img_shape, target_bbox, crop)
        if uv is not None:
            candidate = uv

    if candidate is None:
        uv = _project_with_translation_and_calib(pts, camera, calib, img_shape, target_bbox)
        if uv is not None:
            candidate = uv

    if mode in ("projection", "raw") and candidate is not None:
        return candidate

    return _sanitize_or_fit_overlay(candidate, pts, img_shape, target_bbox)

def skeleton_edges(num_joints: int) -> List[Tuple[int, int]]:
    # Avoid drawing spaghetti when the joint order is unknown. Lines are drawn only
    # for common skeleton sizes; otherwise the report shows joint dots only.
    if num_joints == 24:
        return SKELETON_SMPL_24
    if num_joints == 17:
        return [e for e in SKELETON_17 if max(e) < num_joints]
    if num_joints == 16:
        return [e for e in SKELETON_16 if max(e) < num_joints]
    if num_joints == 25:
        # OpenPose-like body25 approximate topology.
        return [(1,8),(1,2),(2,3),(3,4),(1,5),(5,6),(6,7),(8,9),(9,10),(10,11),(8,12),(12,13),(13,14),(1,0)]
    if num_joints == 33:
        # MediaPipe Pose topology. These indices are already in full image pixels.
        return [
            (11,12),
            (11,13),(13,15),(15,17),(15,19),(15,21),(17,19),
            (12,14),(14,16),(16,18),(16,20),(16,22),(18,20),
            (11,23),(12,24),(23,24),
            (23,25),(25,27),(27,29),(27,31),(29,31),
            (24,26),(26,28),(28,30),(28,32),(30,32),
            (0,1),(1,2),(2,3),(3,7),
            (0,4),(4,5),(5,6),(6,8),
            (9,10)
        ]
    return []

def _edge_is_safe(pa: np.ndarray, pb: np.ndarray, img_shape: Tuple[int, int, int], body_h: float, body_w: float) -> bool:
    """Reject only clearly impossible lines.

    Earlier pruning was too strict, so this keeps known skeleton edges unless an edge is wildly outside the image/body box. This directly addresses the requirement that the visual report should draw the main body connection lines more completely.
    """
    h, w = img_shape[:2]
    if not (np.isfinite(pa).all() and np.isfinite(pb).all()):
        return False
    margin_x = 0.25 * w
    margin_y = 0.25 * h
    if not (-margin_x <= pa[0] <= w + margin_x and -margin_y <= pa[1] <= h + margin_y):
        return False
    if not (-margin_x <= pb[0] <= w + margin_x and -margin_y <= pb[1] <= h + margin_y):
        return False
    d = float(np.linalg.norm(pa[:2] - pb[:2]))
    # Only reject extreme spaghetti edges. Valid side-view arms/legs can be long.
    if d > max(2.2 * body_h, 2.2 * body_w, 0.95 * max(h, w)):
        return False
    return True


def _draw_text_with_bg(img: np.ndarray, text: str, org: Tuple[int, int], scale: float = 0.45,
                       color: Tuple[int, int, int] = (255, 255, 255),
                       bg: Tuple[int, int, int] = (0, 0, 0), thickness: int = 1) -> None:
    x, y = int(org[0]), int(org[1])
    h, w = img.shape[:2]
    text = str(text)
    (tw, th), baseline = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, thickness)
    x = max(2, min(x, max(2, w - tw - 4)))
    y = max(th + 4, min(y, h - baseline - 4))
    cv2.rectangle(img, (x - 2, y - th - 4), (x + tw + 2, y + baseline + 2), bg, -1)
    cv2.putText(img, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, color, thickness, cv2.LINE_AA)


def _draw_pose_layer(out: np.ndarray, pts2d: np.ndarray, edges: List[Tuple[int, int]],
                     joint_errors: Optional[np.ndarray], threshold: float,
                     line_color: Tuple[int, int, int], dot_color: Tuple[int, int, int],
                     bad_color: Tuple[int, int, int], line_thickness: int = 2,
                     dot_radius: int = 4, alpha: float = 1.0,
                     draw_bad: bool = True) -> None:
    """Draw one pose layer on an image.

    The function uses a relaxed edge filter so normal skeleton links are not lost.
    If alpha < 1, the layer is blended after drawing.
    """
    layer = out.copy()
    num_joints = len(pts2d)
    h, w = out.shape[:2]
    bb = _points_bbox(pts2d)
    body_h = h if bb is None else max(bb[3] - bb[1], 1.0)
    body_w = w if bb is None else max(bb[2] - bb[0], 1.0)

    # Draw complete known topology first.
    for a, b in edges:
        if a >= num_joints or b >= num_joints:
            continue
        pa = pts2d[a]
        pb = pts2d[b]
        if not _edge_is_safe(pa, pb, out.shape, body_h, body_w):
            continue
        p1 = tuple(int(round(x)) for x in pa[:2])
        p2 = tuple(int(round(x)) for x in pb[:2])
        cv2.line(layer, p1, p2, line_color, line_thickness, cv2.LINE_AA)

    # Draw joints after edges so the dots are clear.
    for j, p in enumerate(pts2d):
        if not np.isfinite(p).all():
            continue
        if not (-0.25 * w <= p[0] <= 1.25 * w and -0.25 * h <= p[1] <= 1.25 * h):
            continue
        is_bad = False
        if draw_bad and joint_errors is not None and j < len(joint_errors):
            try:
                is_bad = bool(joint_errors[j] >= threshold)
            except Exception:
                is_bad = False
        color = bad_color if is_bad else dot_color
        center = (int(round(p[0])), int(round(p[1])))
        cv2.circle(layer, center, dot_radius, color, -1, cv2.LINE_AA)
        cv2.circle(layer, center, dot_radius + 1, (255, 255, 255), 1, cv2.LINE_AA)

    if alpha >= 0.999:
        out[:] = layer
    else:
        cv2.addWeighted(layer, alpha, out, 1.0 - alpha, 0, dst=out)


def draw_pose(img: np.ndarray, pts2d: np.ndarray, joint_errors: Optional[np.ndarray], threshold: float, label: str, base_color=(0,255,0)) -> np.ndarray:
    out = img.copy()
    num_joints = len(pts2d)
    edges = skeleton_edges(num_joints)
    _draw_pose_layer(
        out, pts2d, edges, joint_errors, threshold,
        line_color=base_color,
        dot_color=base_color,
        bad_color=(0, 0, 255),
        line_thickness=2,
        dot_radius=4,
        alpha=1.0,
        draw_bad=True,
    )
    if False:
        pass
    return out


def draw_student_guidance(
    stu_img: np.ndarray,
    stu_pts: np.ndarray,
    joint_errors: Optional[np.ndarray],
    threshold: float,
    label: str,
    top_k: int = 5,
) -> np.ndarray:
    """Draw the student pose without misleading cross-view overlay.

    Professor-facing design after feedback:
    - The reference/standard pose is drawn on the LEFT image only.
    - The student/current pose is drawn on the RIGHT image only.
    - We do not align/overlay the reference skeleton onto the student image,
      because two videos can have different camera angles. Overlaying different
      viewpoints creates wrong-looking crossing lines.
    - The right image only uses small red rings to mark the student's worst
      failing joints. Exact cm/mm distances are listed in the HTML table below.
    """
    out = stu_img.copy()
    num_joints = len(stu_pts)
    edges = skeleton_edges(num_joints)

    # Student/current pose: yellow skeleton.
    _draw_pose_layer(
        out, stu_pts, edges, None, threshold,
        line_color=(0, 220, 255), dot_color=(0, 220, 255), bad_color=(0, 220, 255),
        line_thickness=2, dot_radius=4, alpha=1.0, draw_bad=False,
    )

    # Mark only the worst failing joints with small red rings. Do not draw any
    # reference skeleton or correction arrows on the student image, because the
    # two images may be from different camera viewpoints.
    if SHOW_TARGET_GUIDE and joint_errors is not None:
        top = top_joint_error_items(joint_errors, top_k=min(top_k, IMAGE_ARROW_JOINTS)) if IMAGE_ARROW_JOINTS > 0 else []
        h, w = out.shape[:2]
        for rank, (idx, err) in enumerate(top, start=1):
            if idx >= len(stu_pts):
                continue
            if not np.isfinite(err) or float(err) < float(threshold):
                continue
            p_cur = stu_pts[idx]
            if not np.isfinite(p_cur).all():
                continue
            if not (-0.25*w <= p_cur[0] <= 1.25*w and -0.25*h <= p_cur[1] <= 1.25*h):
                continue
            center = (int(round(p_cur[0])), int(round(p_cur[1])))
            cv2.circle(out, center, 9, (0, 0, 255), 2, cv2.LINE_AA)
            cv2.circle(out, center, 4, (0, 0, 255), -1, cv2.LINE_AA)
            if not CLEAN_IMAGE_GUIDE:
                label_text = f"#{rank} {format_distance_for_user(err).split('(')[0].strip()}"
                _draw_text_with_bg(out, label_text, (center[0] + 6, center[1] - 6), scale=0.40, color=(255,255,255), bg=(0,0,160), thickness=1)

    return out

def get_video_frame(cap: cv2.VideoCapture, frame_idx: int) -> Optional[np.ndarray]:
    """Read a video frame robustly.

    Some PKL files contain more SMPL frames than the decoded video contains
    (for example, the right MOV can end at frame 624 while the PKL has frames
    up to 647).  The previous frame reader returned None in that situation, so the report
    displayed a blank panel saying "Frame not available".  For a professor/user
    facing report, it is better to show the nearest real video frame instead of
    a blank image.

    Strategy:
      1) try the requested frame;
      2) if it is outside the decoded video range, clamp to the last/first frame;
      3) try nearby frames around the clamped index.
    """
    if cap is None:
        return None
    try:
        requested = int(round(float(frame_idx)))
    except Exception:
        requested = 0

    candidates: List[int] = []
    try:
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    except Exception:
        frame_count = 0

    if frame_count > 0:
        clamped = max(0, min(requested, frame_count - 1))
        candidates.append(requested)
        candidates.append(clamped)
        # Nearby fallback frames.  This handles off-by-one and MOV seeking issues.
        for delta in range(1, 16):
            candidates.append(clamped - delta)
            candidates.append(clamped + delta)
    else:
        candidates.append(requested)
        for delta in range(1, 16):
            candidates.append(requested - delta)
            candidates.append(requested + delta)

    seen = set()
    for cand in candidates:
        if cand in seen:
            continue
        seen.add(cand)
        if cand < 0:
            continue
        if frame_count > 0 and cand >= frame_count:
            continue
        try:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(cand))
            ok, frame = cap.read()
            if ok and frame is not None and getattr(frame, 'size', 0) > 0:
                return frame
        except Exception:
            continue
    return None

def ensure_img(frame: Optional[np.ndarray], size=(1080, 1920, 3), text="Video frame not available") -> np.ndarray:
    if frame is not None:
        return frame
    h, w, c = size
    img = np.full((h, w, c), 245, dtype=np.uint8)
    cv2.putText(img, text, (40, h//2), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0,0,0), 2, cv2.LINE_AA)
    return img


# -----------------------------
# Human-readable error messages
# -----------------------------
def distance_to_mm(value: float) -> float:
    """Convert the internal metric value to millimeters for user-facing text."""
    try:
        return float(value) * DISTANCE_TO_MM
    except Exception:
        return float("nan")


def distance_to_cm(value: float) -> float:
    return distance_to_mm(value) / 10.0


def format_distance_for_user(value: float, include_raw: bool = False) -> str:
    """Return a readable distance such as '12.3 cm (123 mm)'."""
    mm = distance_to_mm(value)
    if not np.isfinite(mm):
        return "không xác định"
    cm = mm / 10.0
    if abs(cm) >= 1.0:
        text = f"{cm:.1f} cm ({mm:.0f} mm)"
    else:
        text = f"{mm:.1f} mm"
    if include_raw:
        text += f"; giá trị nội bộ = {value:.3f}"
    return text


def joint_name_for_index(idx: int) -> str:
    if 0 <= idx < len(SMPL24_JOINT_NAMES):
        vi, en = SMPL24_JOINT_NAMES[idx]
        return f"{vi} ({en})" if SHOW_ENGLISH_JOINT_NAMES else vi
    return f"Khớp #{idx}"


def top_joint_error_items(joint_errors: np.ndarray, top_k: int = 3) -> List[Tuple[int, float]]:
    if joint_errors is None or len(joint_errors) == 0:
        return []
    arr = np.asarray(joint_errors, dtype=float)
    valid = np.where(np.isfinite(arr))[0]
    if len(valid) == 0:
        return []
    order = valid[np.argsort(arr[valid])[::-1]]
    return [(int(i), float(arr[i])) for i in order[:top_k]]


def build_plain_joint_explanation(joint_errors: np.ndarray, avg_error: float, metric: str, threshold: float, top_k: int = 3) -> str:
    """Plain text explanation for terminal/HTML row detail."""
    parts = [
        f"{metric} trung bình của frame này khoảng {format_distance_for_user(avg_error)}.",
        f"Ngưỡng đang đặt: {format_distance_for_user(threshold)}.",
    ]
    if SHOW_RAW_VALUES:
        parts.append(f"Giá trị nội bộ: frame={avg_error:.3f}, ngưỡng={threshold:.3f}.")
    top = top_joint_error_items(joint_errors, top_k=top_k)
    if top:
        joint_texts = []
        for idx, err in top:
            joint_texts.append(f"{joint_name_for_index(idx)} lệch khoảng {format_distance_for_user(err)}")
        parts.append("Các khớp lệch nhiều nhất: " + "; ".join(joint_texts) + ".")
    return " ".join(parts)


def build_html_joint_explanation(joint_errors: np.ndarray, avg_error: float, metric: str, threshold: float, top_k: int = 5) -> str:
    """HTML explanation for each checked frame.
    """
    lines = []
    lines.append(
        f"<b>Ghi chú:</b> {html.escape(metric)} trung bình của frame này ≈ "
        f"<b>{html.escape(format_distance_for_user(avg_error))}</b> "
        f"(ngưỡng ≈ {html.escape(format_distance_for_user(threshold))})."
    )
    top = top_joint_error_items(joint_errors, top_k=top_k)
    if top:
        lines.append("<div class=\"joint-title\">Các khớp lệch nhiều nhất so với vị trí chuẩn:</div>")
        if SHOW_RAW_VALUES:
            lines.append("<table class=\"joint-table\"><thead><tr><th>Khớp</th><th>Khoảng cách lệch</th><th>mm</th><th>raw</th></tr></thead><tbody>")
        else:
            lines.append("<table class=\"joint-table\"><thead><tr><th>Khớp</th><th>Khoảng cách lệch so với chuẩn</th><th>Ý nghĩa</th></tr></thead><tbody>")
        for idx, err in top:
            mm = distance_to_mm(err)
            joint_name = html.escape(joint_name_for_index(idx))
            dist_text = html.escape(format_distance_for_user(err))
            if SHOW_RAW_VALUES:
                lines.append(
                    "<tr><td>" + joint_name + "</td>"
                    "<td><b>" + dist_text + "</b></td>"
                    "<td>" + (f"{mm:.0f}" if np.isfinite(mm) else "-") + "</td>"
                    "<td>" + f"{err:.3f}" + "</td></tr>"
                )
            else:
                lines.append(
                    "<tr><td>" + joint_name + "</td>"
                    "<td><b>" + dist_text + "</b></td>"
                    "<td>Khớp này đang cách vị trí chuẩn khoảng " + dist_text + ".</td></tr>"
                )
        lines.append("</tbody></table>")
        lines.append("<div class=\"small\">Cách đọc: ảnh bên phải chỉ vẽ tư thế học viên; bảng này cho biết các khớp lệch bao xa bằng cm/mm.</div>")
    else:
        lines.append("<span class=\"small\">Không có đủ dữ liệu lỗi theo từng khớp cho frame này.</span>")
    return "".join(lines)


def metric_user_explanation(metric: str) -> str:
    m = metric.upper()
    if m == "MPJPE":
        return (
            "MPJPE là độ lệch trung bình giữa các khớp của học viên và động tác chuẩn sau khi ghép frame bằng DTW. "
            "Nói đơn giản, số này cho biết trung bình các khớp đang cách vị trí chuẩn bao xa."
        )
    if m == "PA-MPJPE":
        return (
            "PA-MPJPE là độ lệch trung bình sau khi đã căn chỉnh hai bộ pose bằng phép biến đổi Procrustes. "
            "Chỉ số này tập trung hơn vào sự khác nhau về tư thế, giảm ảnh hưởng của vị trí/kích thước tổng thể."
        )
    return "Chỉ số này đo độ lệch trung bình giữa pose học viên và pose chuẩn."

# -----------------------------
# HTML report
# -----------------------------
def make_row_image(
    ref_frame: Optional[np.ndarray],
    stu_frame: Optional[np.ndarray],
    ref_pose: np.ndarray,
    stu_pose: np.ndarray,
    joint_errors: np.ndarray,
    threshold: float,
    side: str,
    ref_frame_id: int,
    stu_frame_id: int,
    avg_error: float,
    metric: str,
    calib_ref: Optional[Tuple[float,float,float,float]],
    calib_stu: Optional[Tuple[float,float,float,float]],
    ref_pose2d: Optional[np.ndarray] = None,
    stu_pose2d: Optional[np.ndarray] = None,
    ref_camera: Optional[np.ndarray] = None,
    stu_camera: Optional[np.ndarray] = None,
    ref_bbox: Optional[np.ndarray] = None,
    stu_bbox: Optional[np.ndarray] = None,
    ref_center: Optional[np.ndarray] = None,
    stu_center: Optional[np.ndarray] = None,
    ref_scale: Optional[np.ndarray] = None,
    stu_scale: Optional[np.ndarray] = None,
    ref_crop_size: Optional[np.ndarray] = None,
    stu_crop_size: Optional[np.ndarray] = None,
    ref_vertices: Optional[np.ndarray] = None,
    stu_vertices: Optional[np.ndarray] = None,
) -> np.ndarray:
    ref_img = ensure_img(ref_frame)
    stu_img = ensure_img(stu_frame)

    ref_pts = project_points(ref_pose, calib_ref, ref_img.shape, ref_pose2d, ref_camera, ref_bbox, ref_center, ref_scale, ref_crop_size, ref_vertices, ref_img)
    stu_pts = project_points(stu_pose, calib_stu, stu_img.shape, stu_pose2d, stu_camera, stu_bbox, stu_center, stu_scale, stu_crop_size, stu_vertices, stu_img)

    side_name = side_display_name_vi(side)
    # Left image: standard/reference pose. Right image: student pose.
    # After professor feedback, do not overlay the reference pose onto the
    # student image because the camera viewpoint may differ. Distances are shown
    # in the table below, and only the student's worst failing joints are marked.
    ref_drawn = draw_pose(ref_img, ref_pts, None, threshold, f"Pose chuẩn {side_name} | frame {ref_frame_id}", base_color=(0, 190, 0))
    stu_drawn = draw_student_guidance(
        stu_img, stu_pts, joint_errors, threshold,
        f"Pose học viên {side_name} | frame {stu_frame_id}",
        top_k=TOP_GUIDE_JOINTS,
    )

    # Resize larger for the final report.  The explanatory text is now in HTML,
    # not drawn into the JPEG, so the image looks clean instead of debug-like.
    target_h = REPORT_IMAGE_HEIGHT
    def resize_keep(im):
        h, w = im.shape[:2]
        scale = target_h / max(h, 1)
        return cv2.resize(im, (int(w*scale), target_h))
    ref_small = resize_keep(ref_drawn)
    stu_small = resize_keep(stu_drawn)

    gap = 12
    canvas_h = target_h
    canvas_w = ref_small.shape[1] + stu_small.shape[1] + gap
    canvas = np.full((canvas_h, canvas_w, 3), 248, dtype=np.uint8)
    canvas[:, :ref_small.shape[1]] = ref_small
    canvas[:, ref_small.shape[1]+gap:ref_small.shape[1]+gap+stu_small.shape[1]] = stu_small
    return canvas

def save_html_report(
    report_path: str,
    rows: List[Dict[str, Any]],
    summary: Dict[str, Any],
    ref_folder: str,
    stu_folder: str,
    threshold: float,
    metric: str,
    processed_sides: Optional[List[str]] = None,
    side_rows_map: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    side_summary_map: Optional[Dict[str, List[str]]] = None,
):
    Path(report_path).parent.mkdir(parents=True, exist_ok=True)
    title = f"Báo cáo chấm pose: {os.path.basename(ref_folder)} vs {os.path.basename(stu_folder)}"

    processed_sides = processed_sides or []
    side_rows_map = side_rows_map or {}
    side_summary_map = side_summary_map or {}
    multi_tabs = len(processed_sides) >= 2
    detail_heading = "Danh sách frame đã kiểm tra" if ALLOW_PASS_ROWS and DETAIL_MODE != "failures" else "Danh sách lỗi"

    def _render_rows_table(table_rows: List[Dict[str, Any]], side: Optional[str] = None) -> str:
        include_side_col = side is None
        cols = ["<th style=\"width:70px\">STT</th>"]
        if include_side_col:
            cols.append("<th style=\"width:90px\">Bên</th>")
        cols.extend([
            "<th style=\"width:160px\">Frame ID (video chấm)</th>",
            "<th style=\"width:100px\">Kết quả</th>",
            "<th>Hình minh họa và mô tả dễ hiểu</th>",
        ])
        parts = ["<table>", "  <thead>", "    <tr>" + "".join(cols) + "</tr>", "  </thead>", "  <tbody>"]
        if not table_rows:
            colspan = 5 if include_side_col else 4
            label = side_display_name_vi(side) if side else "hiện tại"
            parts.append(f"<tr><td colspan=\"{colspan}\"><b>Không có frame lỗi cho bên {html.escape(label)} ở ngưỡng hiện tại.</b></td></tr>")
        else:
            for row in table_rows:
                img_rel = html.escape(row["img_rel"])
                side_label = {"left": "Trái", "right": "Phải", "single": "Một video"}.get(row["side"], row["side"])
                detail = html.escape(row["detail"])
                detail_html = row.get("detail_html", "")
                status = row.get("status", "FAIL")
                status_color = "#b00020" if status == "FAIL" else "#087f23"
                status_text = "Chưa đạt" if status == "FAIL" else "Đạt"
                row_index = row.get("side_index", row.get("index", ""))
                tds = [f"<td>{row_index}</td>"]
                if include_side_col:
                    tds.append(f"<td>{side_label}</td>")
                cell_html = (
                    f"<div class=\"frame-note\"><b>Frame học viên {row['stu_frame_id']}</b>: Được so sánh với frame chuẩn tương ứng.</div>"
                    + "<div class=\"panel-labels\"><div class=\"panel-label ref\">1. Ảnh pose chuẩn</div><div class=\"panel-label stu\">2. Ảnh học viên</div></div>"
                    + f"<div style=\"margin-top:8px\"><img class=\"viz\" src=\"{img_rel}\" alt=\"minh họa frame {row.get('index', row_index)}\"></div>"
                    + f"<div class=\"frame-note\">{detail}</div>"
                    + f"<div class=\"explain-box\">{detail_html}</div>"
                )
                tds.extend([
                    f"<td>{row['stu_frame_id']}</td>",
                    f"<td><b style=\"color:{status_color}\">{status_text}</b></td>",
                    f"<td class=\"visual-cell\">{cell_html}</td>",
                ])
                parts.append("    <tr>" + "".join(tds) + "</tr>")
        parts.extend(["  </tbody>", "</table>"])
        return "\n".join(parts)

    html_parts = []
    html_parts.append(f"""<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
body {{ font-family: Arial, Helvetica, sans-serif; margin: 22px; line-height: 1.52; color:#1f1f1f; background:#fafafa; }}
h1,h2,h3 {{ margin-bottom: 8px; }}
h1 {{ color:#174b25; letter-spacing:.1px; }}
code, pre {{ background: #f4f4f4; padding: 2px 6px; border-radius: 4px; }}
table {{ border-collapse: collapse; width: 100%; margin-top: 16px; background:#fff; }}
th, td {{ border: 1px solid #d0d0d0; padding: 10px; vertical-align: top; }}
th {{ background: #f1f7f1; color:#153f1e; }}
.summary-box {{ background: #f7fff7; border: 1px solid #9bd49b; padding: 18px; border-radius: 12px; margin-bottom: 20px; box-shadow:0 2px 10px rgba(0,0,0,.04); }}
.compact-box p {{ margin:8px 0 0 0; }}
.badge {{ display: inline-block; padding: 5px 12px; border-radius: 999px; background: #e8f6e8; border:1px solid #b9dfb9; margin-right: 8px; margin-bottom:6px; }}
.small {{ color: #555; font-size: 14px; }}
.section-note {{ background:#eef8ef; border:1px solid #b6d8b8; border-radius:10px; padding:14px 16px; margin:14px 0 18px 0; }}
.policy-grid {{ display:none; }}
.policy-card {{ border-radius:12px; padding:14px 16px; background:white; box-shadow:0 2px 10px rgba(0,0,0,.05); }}
.policy-card.good {{ border:1px solid #8fd18f; background:#f7fff7; }}
.policy-card.bad {{ border:1px solid #f0aaaa; background:#fff7f7; }}
.policy-title {{ font-weight:800; font-size:18px; margin-bottom:8px; }}
.panel-labels {{ display:grid; grid-template-columns:1fr 1fr; gap:12px; max-width:1150px; margin:8px auto 6px auto; }}
.panel-label {{ border-radius:8px; padding:8px 10px; color:white; font-weight:700; text-align:center; }}
.panel-label.ref {{ background:#0b7d24; }}
.panel-label.stu {{ background:#d59a00; }}
img.viz {{ max-width: min(100%, 1150px); height: auto; border: 1px solid #cfcfcf; border-radius: 10px; display:block; margin-left:auto; margin-right:auto; background:white; }}
ul {{ margin-top: 6px; }}
.explain-box {{ background: #fffdf5; border: 1px solid #ffe08a; padding: 12px 14px; border-radius: 10px; margin-top: 12px; }}
.joint-list {{ margin-top: 6px; margin-bottom: 4px; }}
.joint-list li {{ margin-bottom: 3px; }}
.joint-title {{ font-weight: bold; margin-top: 10px; }}
.joint-table {{ margin-top: 8px; width: 100%; border-collapse: collapse; }}
.joint-table th, .joint-table td {{ border: 1px solid #e0d4aa; padding: 6px 8px; }}
.legend-box {{ background: #f4fff4; border: 1px solid #9ed79e; padding: 14px 16px; border-radius: 12px; margin-top: 10px; }}
.k-green {{ color: #087f23; font-weight: bold; }}
.k-yellow {{ color: #9a6b00; font-weight: bold; }}
.k-red {{ color: #b00020; font-weight: bold; }}
.tab-bar {{ display: flex; gap: 10px; margin-top: 18px; margin-bottom: 10px; flex-wrap: wrap; }}
.tab-btn {{ border: 1px solid #8dc48d; background: #f2fff2; color: #0f4018; border-radius: 999px; padding: 10px 18px; cursor: pointer; font-weight: bold; }}
.tab-btn.active {{ background: #0b7d24; color:white; }}
.tab-panel {{ display: none; }}
.tab-panel.active {{ display: block; }}
.side-box {{ background: #ffffff; border: 1px solid #c9e7c9; padding: 12px 14px; border-radius: 10px; margin-top: 10px; }}
.visual-cell {{ min-width: 820px; text-align:center; }}
.frame-note {{ margin: 8px auto 0 auto; color: #333; font-size: 14px; max-width: 1150px; text-align:left; }}
@media (max-width: 900px) {{ .policy-grid, .panel-labels {{ grid-template-columns:1fr; }} .visual-cell {{ min-width: 0; }} }}
</style>
<script>
function openPoseTab(sideKey) {{
  var buttons = document.querySelectorAll('.tab-btn');
  var panels = document.querySelectorAll('.tab-panel');
  buttons.forEach(function(btn) {{ btn.classList.remove('active'); }});
  panels.forEach(function(panel) {{ panel.classList.remove('active'); }});
  var activeBtn = document.getElementById('tabbtn-' + sideKey);
  var activePanel = document.getElementById('tabpanel-' + sideKey);
  if (activeBtn) activeBtn.classList.add('active');
  if (activePanel) activePanel.classList.add('active');
}}
</script>
</head>
<body>
<h1>{html.escape(title)}</h1>

<div class="summary-box compact-box">
  <div><span class="badge"><b>Pose chuẩn</b> {html.escape(os.path.basename(ref_folder))}</span>
       <span class="badge"><b>Học viên</b> {html.escape(os.path.basename(stu_folder))}</span>
       <span class="badge"><b>Chỉ số</b> {html.escape(metric)}</span>
       <span class="badge"><b>Ngưỡng</b> {threshold:g}</span></div>
  <p>{summary['score_html']}</p>
  <p class="small">Mỗi ảnh chỉ vẽ skeleton của đúng người trong ảnh.</p>
</div>

<h2>{html.escape(detail_heading)}</h2>
""")

    if multi_tabs:
        html_parts.append("<div class=\"small\">Báo cáo có 2 tab: Bên Trái và Bên Phải. Mỗi tab chỉ hiển thị danh sách lỗi của bên tương ứng.</div>")
        html_parts.append("<div class=\"tab-bar\">")
        for idx, side in enumerate(processed_sides):
            key = html.escape(side)
            label = side_display_name_vi(side)
            active_cls = " active" if idx == 0 else ""
            html_parts.append(f"<button type=\"button\" class=\"tab-btn{active_cls}\" id=\"tabbtn-{key}\" onclick=\"openPoseTab('{key}')\">Bên {html.escape(label)}</button>")
        html_parts.append("</div>")
        for idx, side in enumerate(processed_sides):
            key = html.escape(side)
            label = side_display_name_vi(side)
            active_cls = " active" if idx == 0 else ""
            html_parts.append(f"<div class=\"tab-panel{active_cls}\" id=\"tabpanel-{key}\">")
            html_parts.append(f"<h3>Bên {html.escape(label)}</h3>")
            html_parts.append(_render_rows_table(side_rows_map.get(side, []), side=side))
            html_parts.append("</div>")
    else:
        html_parts.append(_render_rows_table(rows, side=processed_sides[0] if processed_sides else None))

    html_parts.append("""
<script>
(function() {
  var first = document.querySelector('.tab-btn');
  if (first) { first.click(); }
})();
</script>
</body>
</html>
""")
    Path(report_path).write_text("".join(html_parts), encoding="utf-8")

# -----------------------------
# Side processing
# -----------------------------
def _frame_optional(seq: Optional[np.ndarray], idx: int) -> Optional[np.ndarray]:
    if seq is None or len(seq) == 0:
        return None
    if idx < len(seq):
        return seq[idx]
    return seq[-1]


def process_side(
    side: str,
    ref_data: PoseData,
    stu_data: PoseData,
    ref_video_path: Optional[str],
    stu_video_path: Optional[str],
    ref_calib_path: Optional[str],
    stu_calib_path: Optional[str],
    threshold: float,
    metric: str,
    assets_dir: str,
    index_offset: int = 0,
) -> Tuple[float, List[str], List[Dict[str, Any]], int]:
    ref_pose = ref_data.joints3d
    stu_pose = stu_data.joints3d
    path, _ = dtw_align(ref_pose, stu_pose, metric)

    failing_rows: List[Dict[str, Any]] = []
    failing_summary_pairs: List[Tuple[int, float]] = []

    # score is on student frames
    total_stu_frames = len(path)
    pass_count = 0

    ref_cap = cv2.VideoCapture(ref_video_path) if ref_video_path and os.path.exists(ref_video_path) else None
    stu_cap = cv2.VideoCapture(stu_video_path) if stu_video_path and os.path.exists(stu_video_path) else None

    ref_calib = load_calib(ref_calib_path)
    stu_calib = load_calib(stu_calib_path)

    try:
        for idx_in_side, (ri, sj) in enumerate(path, start=1):
            ref_frame_pose = ref_pose[ri]
            stu_frame_pose = stu_pose[sj]
            avg_error, joint_errors = frame_distance_with_joints(ref_frame_pose, stu_frame_pose, metric)

            is_fail = bool(avg_error >= threshold)
            if not is_fail:
                pass_count += 1
            else:
                failing_summary_pairs.append((sj, avg_error))

            # The score/error summary always uses true failures only.
            # Professor-facing tables must be true error lists: PASS/Đạt rows are
            # hidden by default even if someone selects sample/all mode.
            show_row = is_fail
            if ALLOW_PASS_ROWS:
                if DETAIL_MODE == "all":
                    show_row = True
                elif DETAIL_MODE == "sample" and (idx_in_side == 1 or sj % SAMPLE_EVERY == 0):
                    show_row = True

            if not show_row:
                continue
            if MAX_HTML_ROWS is not None and len(failing_rows) >= MAX_HTML_ROWS:
                continue

            ref_frame = get_video_frame(ref_cap, ri) if ref_cap is not None else None
            stu_frame = get_video_frame(stu_cap, sj) if stu_cap is not None else None

            combined = make_row_image(
                ref_frame, stu_frame,
                ref_frame_pose, stu_frame_pose,
                joint_errors, threshold, side, ri, sj, avg_error, metric,
                ref_calib, stu_calib,
                _frame_optional(ref_data.joints2d, ri), _frame_optional(stu_data.joints2d, sj),
                _frame_optional(ref_data.camera, ri), _frame_optional(stu_data.camera, sj),
                _frame_optional(ref_data.bbox, ri), _frame_optional(stu_data.bbox, sj),
                _frame_optional(ref_data.center, ri), _frame_optional(stu_data.center, sj),
                _frame_optional(ref_data.scale, ri), _frame_optional(stu_data.scale, sj),
                _frame_optional(ref_data.crop_size, ri), _frame_optional(stu_data.crop_size, sj),
                _frame_optional(ref_data.vertices3d, ri), _frame_optional(stu_data.vertices3d, sj),
            )
            file_name = f"{index_offset + len(failing_rows) + 1:05d}_{side}_stu_{sj}_ref_{ri}.jpg"
            img_path = os.path.join(assets_dir, file_name)
            cv2.imwrite(img_path, combined, [int(cv2.IMWRITE_JPEG_QUALITY), 92])

            human_detail = build_plain_joint_explanation(joint_errors, avg_error, metric, threshold, top_k=5)
            status = "FAIL" if is_fail else "PASS"
            if is_fail:
                detail_prefix = f"Frame học viên {sj} được so sánh với frame chuẩn {ri}. Frame này chưa đạt ngưỡng vì {metric} trung bình khoảng {format_distance_for_user(avg_error)}. "
            else:
                detail_prefix = f"Frame học viên {sj} được so sánh với frame chuẩn {ri}. Frame này đạt ngưỡng; bảng chỉ hiển thị để đối chiếu khi bật chế độ xem thêm. "
            row = {
                "index": index_offset + len(failing_rows) + 1,
                "side_index": len(failing_rows) + 1,
                "side": side,
                "stu_frame_id": sj,
                "status": status,
                "img_rel": os.path.relpath(img_path, os.path.dirname(os.path.join(assets_dir, "..", "report.html"))).replace("\\", "/"),
                "detail": detail_prefix + human_detail,
                "detail_html": build_html_joint_explanation(joint_errors, avg_error, metric, threshold, top_k=5),
            }
            failing_rows.append(row)
    finally:
        if ref_cap is not None:
            ref_cap.release()
        if stu_cap is not None:
            stu_cap.release()

    score = 100.0 * pass_count / max(total_stu_frames, 1)
    segs = group_error_segments(failing_summary_pairs)
    summary_lines = []
    side_vi = side_display_name_vi(side)
    if not segs:
        summary_lines.append(f"{side_vi}: Empty")
    else:
        summary_lines.append(f"{side_vi}: {len(failing_summary_pairs)}/{total_stu_frames} frame chưa đạt ngưỡng {threshold:g} theo {metric} (ngưỡng xấp xỉ {format_distance_for_user(threshold)}).")
        for s, e, mean_e, max_e in segs:
            summary_lines.append(f"- {side_vi} frame {s}-{e}: lỗi trung bình khoảng {format_distance_for_user(mean_e)}; lỗi lớn nhất khoảng {format_distance_for_user(max_e)}.")
    return score, summary_lines, failing_rows, index_offset + len(failing_rows)

# -----------------------------
# Main
# -----------------------------
def main():
    raw_lines = [line.rstrip("\r\n") for line in sys.stdin.readlines()]
    raw_lines = [x for x in raw_lines if x.strip() != ""]
    if len(raw_lines) < 4:
        raise SystemExit("Need 4 input lines: ref_folder, student_folder, threshold, metric")

    ref_input = raw_lines[0].strip()
    stu_input = raw_lines[1].strip()
    threshold = float(raw_lines[2].strip())
    metric = raw_lines[3].strip().upper()

    # allow folder names relative to current directory
    cwd = os.getcwd()
    ref_folder = ref_input if os.path.isdir(ref_input) else os.path.join(cwd, ref_input)
    stu_folder = stu_input if os.path.isdir(stu_input) else os.path.join(cwd, stu_input)

    if not os.path.isdir(ref_folder):
        raise FileNotFoundError(f"Reference folder not found: {ref_folder}")
    if not os.path.isdir(stu_folder):
        raise FileNotFoundError(f"Student folder not found: {stu_folder}")

    ref_files = find_side_files(ref_folder)
    stu_files = find_side_files(stu_folder)
    sides = available_eval_sides(ref_files, stu_files)
    if not sides:
        raise FileNotFoundError(
            "No matching PKL pair found. Put either left/right PKLs in both folders, "
            "or exactly one PKL in each folder for single-video grading."
        )

    base_name = f"{os.path.basename(ref_folder)}_vs_{os.path.basename(stu_folder)}_{metric}_th{str(threshold).replace('.', '_')}_bao_cao_cuoi"
    reports_dir = os.path.join(cwd, "html_reports", base_name)
    if os.path.isdir(reports_dir):
        shutil.rmtree(reports_dir)
    assets_dir = os.path.join(reports_dir, "assets")
    os.makedirs(assets_dir, exist_ok=True)
    report_path = os.path.join(reports_dir, "report.html")

    next_idx = 0
    all_rows: List[Dict[str, Any]] = []
    all_lines: List[str] = []
    side_scores: Dict[str, float] = {}
    side_rows_map: Dict[str, List[Dict[str, Any]]] = {}
    side_summary_map: Dict[str, List[str]] = {}
    processed_sides: List[str] = []

    print("Matched input files:", file=sys.stderr)
    for side in sides:
        ref_pkl = ref_files["pkl"].get(side)
        stu_pkl = stu_files["pkl"].get(side)
        if not ref_pkl or not stu_pkl:
            continue
        print(f"- {side_display_name(side)} PKL: ref={ref_pkl} | student={stu_pkl}", file=sys.stderr)
        ref_data = load_pose_pkl(ref_pkl)
        stu_data = load_pose_pkl(stu_pkl)
        score, lines, rows, next_idx = process_side(
            side, ref_data, stu_data,
            ref_files["video"].get(side), stu_files["video"].get(side),
            ref_files["calib"].get(side), stu_files["calib"].get(side),
            threshold, metric, assets_dir, next_idx
        )
        side_scores[side] = score
        side_rows_map[side] = rows
        side_summary_map[side] = lines
        processed_sides.append(side)
        all_lines.extend(lines)
        all_rows.extend(rows)

    if not side_scores:
        raise RuntimeError("No side was processed successfully.")

    # Professor requirement: if there is only one pair, final score equals that pair score.
    final_score = float(np.mean(list(side_scores.values())))

    # plain-text output
    print(f"{final_score:.2f}".rstrip("0").rstrip("."))
    if all("Empty" in line for line in all_lines):
        print("Danh sach loi: Empty")
    else:
        print("Danh sach loi:")
        for line in all_lines:
            if line.endswith("Empty"):
                continue
            print(line)

    # html summary
    error_html = ["<ul>"]
    for line in all_lines:
        error_html.append(f"<li>{html.escape(line)}</li>")
    error_html.append("</ul>")
    score_bits = []
    for side, score in side_scores.items():
        score_bits.append(f"<b>Điểm bên {html.escape(side_display_name_vi(side))}:</b> {score:.2f}")
    score_bits.append(f"<b>Điểm cuối:</b> {final_score:.2f}")
    summary = {
        "side_scores": side_scores,
        "final_score": final_score,
        "score_html": " &nbsp; | &nbsp; ".join(score_bits),
        "error_html": "".join(error_html),
    }

    # fix img_rel after report_path known
    for row in all_rows:
        img_name = os.path.basename(row["img_rel"])
        abs_img = os.path.join(assets_dir, img_name)
        row["img_rel"] = os.path.relpath(abs_img, reports_dir).replace("\\", "/")

    save_html_report(
        report_path, all_rows, summary, ref_folder, stu_folder, threshold, metric,
        processed_sides=processed_sides,
        side_rows_map=side_rows_map,
        side_summary_map=side_summary_map,
    )

    print(f"HTML report: {report_path}")

if __name__ == "__main__":
    main()
