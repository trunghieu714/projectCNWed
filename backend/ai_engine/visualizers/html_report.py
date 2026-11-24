"""
Báo cáo HTML kết quả đối sánh DTW (Slide 8: "đối sánh động tác bằng DTW, lưu lại dạng HTML").

Theo bố cục code mẫu của giảng viên (FAQ Q8): bài nộp 2 video có 2 tab "Bên Trái" / "Bên Phải",
mỗi tab chỉ chứa danh sách lỗi của góc quay đó. Tab dùng CSS thuần (không JavaScript) để
hiển thị được cả khi nhúng trong iframe sandbox ở bình luận của bài viết.
"""
import html
import os
from typing import Any, Dict, List, Optional

SIDE_LABELS = {"left": "Bên Trái", "right": "Bên Phải", "fused": "Fusion 2 góc quay"}

_CSS = """
body{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;margin:0;background:#f5f6f8;color:#1c1e21}
.wrap{max-width:900px;margin:0 auto;padding:16px}
.card{background:#fff;border:1px solid #dddfe2;border-radius:10px;padding:16px;margin-bottom:12px}
h1{font-size:20px;margin:0 0 4px}.muted{color:#65676b;font-size:13px}
.score{font-size:40px;font-weight:800}.ok{color:#2e7d32}.mid{color:#ed6c02}.bad{color:#c62828}
.tabs input{display:none}.tabs label{display:inline-block;padding:8px 16px;border-radius:8px 8px 0 0;
border:1px solid #dddfe2;border-bottom:none;background:#e4e6eb;cursor:pointer;font-weight:600;font-size:14px}
.tabs input:checked+label{background:#fff;color:#1877f2}
.panel{display:none;background:#fff;border:1px solid #dddfe2;border-radius:0 10px 10px 10px;padding:16px}
table{width:100%;border-collapse:collapse;font-size:13px}th,td{border-bottom:1px solid #eee;padding:6px 8px;text-align:left}
th{background:#f0f2f5}.pill{display:inline-block;background:#fdecea;color:#c62828;border-radius:10px;padding:1px 8px;margin:1px;font-size:12px}
.grid{display:flex;gap:16px;flex-wrap:wrap}.grid div{flex:1;min-width:140px}
"""

def _score_class(score: float) -> str:
    return "ok" if score >= 80 else ("mid" if score >= 60 else "bad")

def _chart(per_frame: List[Dict[str, Any]], tolerance: float, width: int = 840, height: int = 160) -> str:
    if not per_frame:
        return ""
    errs = [p["error"] for p in per_frame]
    ymax = max(max(errs), tolerance * 1.5, 1e-6)
    n = len(errs)
    def x(i): return 30 + (width - 40) * i / max(n - 1, 1)
    def y(v): return 10 + (height - 30) * (1 - v / ymax)
    pts = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(errs))
    ty = y(tolerance)
    return (
        f'<svg viewBox="0 0 {width} {height}" width="100%" role="img" aria-label="Sai số theo thời gian">'
        f'<line x1="30" y1="{height-20}" x2="{width-10}" y2="{height-20}" stroke="#ccc"/>'
        f'<line x1="30" y1="{ty:.1f}" x2="{width-10}" y2="{ty:.1f}" stroke="#c62828" stroke-dasharray="4 3"/>'
        f'<text x="{width-12}" y="{ty-4:.1f}" font-size="11" fill="#c62828" text-anchor="end">ngưỡng {int(tolerance*100)}%</text>'
        f'<polyline points="{pts}" fill="none" stroke="#1877f2" stroke-width="1.8"/>'
        f'<text x="30" y="{height-4}" font-size="11" fill="#65676b">Bắt đầu</text>'
        f'<text x="{width-10}" y="{height-4}" font-size="11" fill="#65676b" text-anchor="end">Kết thúc</text>'
        "</svg>"
    )

def _side_panel(side: str, res: Dict[str, Any]) -> str:
    segs = res.get("segments", [])
    rows = "".join(
        "<tr>"
        f"<td>{i + 1}</td><td>{s['time_start']:.1f}s – {s['time_end']:.1f}s</td>"
        f"<td>{s['coach_start']} – {s['coach_end']}</td>"
        f"<td>{s['max_error_percent']}%</td>"
        f"<td>{''.join(f'<span class=pill>{html.escape(j)}</span>' for j in s['worst_joints'])}</td>"
        "</tr>"
        for i, s in enumerate(segs)
    ) or '<tr><td colspan="5">Không phát hiện đoạn sai nào vượt ngưỡng. 🎉</td></tr>'
    joints = sorted(res.get("joint_mean_errors", {}).items(), key=lambda kv: -kv[1])[:5]
    joint_rows = "".join(f"<tr><td>{html.escape(k)}</td><td>{v}%</td></tr>" for k, v in joints)
    mm = res.get("mean_pa_mpjpe")
    mm_html = f"<div><div class=muted>PA-MPJPE trung bình</div><b>{mm} {res.get('unit','')}</b></div>" if mm is not None else ""
    return (
        f"<div class=grid><div><div class=muted>Điểm {SIDE_LABELS.get(side, side)}</div>"
        f"<div class='score {_score_class(res.get('final_score', 0))}'>{res.get('final_score', 0)}</div></div>"
        f"{mm_html}<div><div class=muted>Số đoạn sai</div><b>{len(segs)}</b></div>"
        f"<div><div class=muted>Nguồn pose</div><b>{html.escape(str(res.get('pose_source', '')))}</b></div></div>"
        f"<h3>Sai số theo thời gian</h3>{_chart(res.get('per_frame_error', []), res.get('tolerance', 0.12))}"
        "<h3>Danh sách lỗi</h3><table><tr><th>#</th><th>Thời điểm (video HV)</th><th>Frame HLV</th>"
        f"<th>Lệch tối đa</th><th>Khớp sai nhiều nhất</th></tr>{rows}</table>"
        f"<h3>Khớp lệch trung bình lớn nhất</h3><table><tr><th>Khớp</th><th>Sai số tương đối</th></tr>{joint_rows}</table>"
    )

class HtmlReportRenderer:
    def render(self, result: Dict[str, Any], output_path: Optional[str] = None, title: str = "Kết quả chấm điểm động tác") -> str:
        sides: Dict[str, Dict[str, Any]] = result.get("sides", {})
        score = result.get("score", 0.0)
        tabs = []
        for k, (side, res) in enumerate(sides.items()):
            sid = f"tab_{side}"
            tabs.append(
                f'<input type="radio" name="side" id="{sid}" {"checked" if k == 0 else ""}>'
                f'<label for="{sid}">{SIDE_LABELS.get(side, side)}</label>'
            )
        panels = "".join(f'<div class="panel" id="panel_{s}">{_side_panel(s, r)}</div>' for s, r in sides.items())
        # CSS thuần: radio thứ k được chọn -> hiện panel thứ k
        show_rules = "".join(
            f"#tab_{s}:checked ~ .panels #panel_{s}{{display:block}}" for s in sides.keys()
        )
        doc = (
            "<!doctype html><html lang='vi'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{html.escape(title)}</title><style>{_CSS}{show_rules}</style></head><body><div class=wrap>"
            f"<div class=card><h1>{html.escape(title)}</h1>"
            f"<div class='score {_score_class(score)}'>{score}/100</div>"
            f"<p>{html.escape(result.get('summary', ''))}</p>"
            f"<div class=muted>Thuật toán: DTW (cửa sổ Sakoe-Chiba) trên khoảng cách {html.escape(result.get('metric', 'PA-MPJPE'))}</div></div>"
            f"<div class=tabs>{''.join(tabs)}<div class=panels>{panels}</div></div>"
            "</div></body></html>"
        )
        if output_path:
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(doc)
        return doc
