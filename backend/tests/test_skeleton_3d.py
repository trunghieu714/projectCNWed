"""Kiểm thử dữ liệu trình xem khung xương 3D và báo cáo HTML (bản đầy đủ / bản gọn nhúng bình luận)."""
import json
import re

import numpy as np

from ai_engine.pose_io import axis_angle_to_matrix, smpl_forward_kinematics
from ai_engine.visualizers.html_report import HtmlReportRenderer
from ai_engine.visualizers.skeleton_3d import build_viewer_data

def _motion(n=60, seed=0):
    rng = np.random.default_rng(seed)
    t = np.linspace(0, 2 * np.pi, n)[:, None]
    aa = np.zeros((n, 24, 3))
    aa[:, 1:, :] = rng.normal(0, 0.15, (1, 23, 3)) + 0.4 * np.sin(t)[:, :, None] * rng.normal(0, 1, (1, 23, 3))
    return smpl_forward_kinematics(aa.reshape(n, 72))

def test_viewer_aligns_rotated_student_and_points_head_up():
    coach = _motion()
    # HV = cùng động tác nhưng bị xoay, phóng to và dời chỗ (như quay ở góc khác / người cao hơn)
    rot = axis_angle_to_matrix(np.array([0.3, 1.2, -0.4]))
    student = 1.3 * coach @ rot.T + np.array([2.0, -1.0, 5.0])
    path = [(i, i) for i in range(len(coach))]
    data = build_viewer_data(coach, student, path, tolerance=0.12, student_frame_times=[i / 30 for i in range(60)])
    assert data and len(data["bones"]) == 23 and len(data["names"]) == 24
    f = data["frames"][10]
    assert max(f["e"]) < 1e-3                                  # Procrustes khử hết xoay / tỉ lệ / dời chỗ
    assert np.allclose(f["c"], f["s"], atol=2e-3)
    head, pelvis = data["names"].index("Đầu"), 0
    assert all(fr["c"][head][1] > fr["c"][pelvis][1] for fr in data["frames"])   # đầu ở trên xương chậu
    assert f["t"] == round(10 / 30, 2)

def test_viewer_flags_wrong_joints_and_limits_size():
    coach = _motion(500)
    student = coach.copy()
    student[:, 21] += np.array([0.6, 0.0, 0.0])                # cổ tay phải lệch hẳn
    data = build_viewer_data(coach, student, [(i, i) for i in range(500)], tolerance=0.12)
    assert len(data["frames"]) <= 180
    wrist = data["names"].index("Cổ tay phải")
    assert all(fr["e"][wrist] > 0.12 for fr in data["frames"])
    assert build_viewer_data(coach, student, [], 0.12) is None

def test_report_full_has_viewer_compact_does_not(tmp_path):
    coach = _motion()
    data = build_viewer_data(coach, coach, [(i, i) for i in range(60)], 0.12)
    result = {"score": 91.0, "summary": "Tốt </script><b>x</b>", "metric": "PA-MPJPE",
              "sides": {"left": {"final_score": 91.0, "segments": [], "per_frame_error": [], "tolerance": 0.12}}}
    out = tmp_path / "report.html"
    compact = HtmlReportRenderer().render(result, str(out), viewers={"left": data})
    full = out.read_text(encoding="utf-8")
    assert "class=sk3d" in full and "<canvas" in full and "requestAnimationFrame" in full
    assert "class=sk3d" not in compact and "Xem 3D" in compact and "Bên Trái" in compact
    payload = re.search(r"<script type='application/json'>(.*?)</script>", full, re.S).group(1)
    assert json.loads(payload)["frames"][0]["cf"] == 0             # JSON nhúng đọc lại được
    assert "</script><b>" not in full                              # nội dung người dùng đã được escape
    # Báo cáo cũ (JS cũ) -> refresh_viewer thay JS, giữ nguyên dữ liệu; dữ liệu 3D đọc lại được từ báo cáo
    from ai_engine.visualizers.html_report import extract_viewer_data, refresh_viewer, write_skeleton_json
    old = full.replace(full[full.rfind("<script>"):full.rfind("</script>")], "<script>/*old*/")
    new = refresh_viewer(old)
    assert "/*old*/" not in new and "requestAnimationFrame" in new
    assert new.count("application/json") == full.count("application/json")
    assert refresh_viewer("<html>không có 3D</html>") is None
    assert extract_viewer_data(full) == {"left": json.loads(json.dumps(data))}
    path = write_skeleton_json(str(tmp_path / "skeleton3d.json"), extract_viewer_data(full))
    assert json.loads(open(path, encoding="utf-8").read())["sides"]["left"]["bones"] == [list(b) for b in data["bones"]]
    assert write_skeleton_json(str(tmp_path / "none.json"), {}) is None
    # Không có dữ liệu 3D -> file và bản trả về giống nhau, không chèn JS
    plain = HtmlReportRenderer().render(result, str(tmp_path / "r2.html"))
    assert plain == (tmp_path / "r2.html").read_text(encoding="utf-8") and "<script>" not in plain
