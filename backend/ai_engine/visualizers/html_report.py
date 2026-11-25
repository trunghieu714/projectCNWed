"""
Báo cáo HTML kết quả đối sánh DTW (Slide 8: "đối sánh động tác bằng DTW, lưu lại dạng HTML").

Theo bố cục code mẫu của giảng viên (FAQ Q8): bài nộp 2 video có 2 tab "Bên Trái" / "Bên Phải",
mỗi tab chỉ chứa danh sách lỗi của góc quay đó. Tab dùng CSS thuần (không JavaScript) để
hiển thị được cả khi nhúng trong iframe sandbox ở bình luận của bài viết.

File report.html (bản đầy đủ) có thêm trình xem khung xương 3D HLV - HV xoay được (JavaScript, mở ở tab riêng);
bản trả về để nhúng vào bình luận (detail_mistakes) không kèm dữ liệu 3D cho gọn.
"""
import html
import json
import os
import re
from typing import Any, Dict, List, Optional

_VIEWER_JS_PATH = os.path.join(os.path.dirname(__file__), "skeleton_viewer.js")

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
.sk3d canvas{width:100%;height:420px;background:#fafbfc;border:1px solid #dddfe2;border-radius:8px;touch-action:none;cursor:grab}
.sk-bar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:8px 0;font-size:13px}.sk-bar input[type=range]{flex:1;min-width:160px}
.sk-bar button,.sk-bar select{font:inherit;padding:4px 10px;border:1px solid #dddfe2;border-radius:6px;background:#fff;cursor:pointer}
.sk-legend span{display:inline-block;width:10px;height:10px;border-radius:50%;margin:0 4px 0 10px;vertical-align:middle}
.note{background:#e7f3ff;border:1px solid #b6d4fe;border-radius:8px;padding:10px;font-size:13px}
"""

def _json_for_script(data: Any) -> str:
    """JSON nhúng an toàn trong <script> (không để chuỗi '</' đóng thẻ sớm)."""
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")

def _viewer_block(side: str, data: Dict[str, Any]) -> str:
    return (
        f"<h3>Khung xương 3D HLV – HV (kéo để xoay, lăn chuột để phóng to)</h3><div class=sk3d id='sk3d_{side}'>"
        f"<script type='application/json'>{_json_for_script(data)}</script>"
        "<div class='sk-bar'><button type=button class=sk-play>⏸ Dừng</button>"
        "<input type=range class=sk-slider min=0 value=0 aria-label='Tua theo thời gian'>"
        "<select class=sk-mode aria-label='Chế độ hiển thị'><option value=overlay>Chồng lên nhau</option>"
        "<option value=side>Cạnh nhau</option><option value=coach>Chỉ HLV</option><option value=student>Chỉ HV</option></select></div>"
        "<canvas aria-label='Khung xương 3D'></canvas>"
        "<div class='sk-bar sk-legend'><span style='background:#1877f2'></span>HLV<span style='background:#2e7d32'></span>HV"
        f"<span style='background:#c62828'></span>Khớp lệch quá ngưỡng {int(data.get('tolerance', 0.12) * 100)}%</div>"
        "<div class='muted sk-info'></div>"
        "<noscript><div class=note>Trình xem 3D cần JavaScript: mở báo cáo này ở tab riêng của trình duyệt.</div></noscript></div>"
    )

_VIEWER_NOTE = ("<div class=note>🧍 Khung xương 3D HLV – HV xoay được có trong báo cáo đầy đủ: "
                "bấm nút <b>Xem 3D</b> dưới bình luận điểm, hoặc mở report.html trong file kết quả (.zip).</div>")

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

def _side_panel(side: str, res: Dict[str, Any], viewer: str = "") -> str:
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
        f"{viewer}"
        f"<h3>Sai số theo thời gian</h3>{_chart(res.get('per_frame_error', []), res.get('tolerance', 0.12))}"
        "<h3>Danh sách lỗi</h3><table><tr><th>#</th><th>Thời điểm (video HV)</th><th>Frame HLV</th>"
        f"<th>Lệch tối đa</th><th>Khớp sai nhiều nhất</th></tr>{rows}</table>"
        f"<h3>Khớp lệch trung bình lớn nhất</h3><table><tr><th>Khớp</th><th>Sai số tương đối</th></tr>{joint_rows}</table>"
    )

def refresh_viewer(doc: str) -> Optional[str]:
    """
    Cập nhật JavaScript trình xem 3D của một report.html đã tạo trước đó lên bản hiện tại
    (dữ liệu chấm và khung xương giữ nguyên). Trả về None nếu báo cáo không có trình xem 3D.
    """
    if "class=sk3d" not in doc:
        return None
    with open(_VIEWER_JS_PATH, encoding="utf-8") as f:
        script = f"<script>{f.read()}</script>"
    # Script trình xem là thẻ <script> cuối cùng không mang type='application/json'
    start = doc.rfind("<script>")
    end = doc.find("</script>", start)
    if start < 0 or end < 0:
        return None
    return doc[:start] + script + doc[end + len("</script>"):]

def extract_viewer_data(doc: str) -> Dict[str, Dict[str, Any]]:
    """Đọc lại dữ liệu khung xương 3D {góc quay: dữ liệu} nhúng trong một report.html (cho báo cáo tạo trước đây)."""
    out: Dict[str, Dict[str, Any]] = {}
    for m in re.finditer(r"<div class=sk3d id='sk3d_(\w+)'><script type='application/json'>(.*?)</script>", doc, re.S):
        try:
            out[m.group(1)] = json.loads(m.group(2).replace("<\\/", "</"))
        except json.JSONDecodeError:
            continue
    return out

def write_skeleton_json(path: str, viewers: Dict[str, Dict[str, Any]]) -> Optional[str]:
    """Ghi skeleton3d.json {"sides": {góc quay: dữ liệu}} để trang web vẽ khung xương 3D cạnh video."""
    viewers = {s: v for s, v in (viewers or {}).items() if v}
    if not viewers:
        return None
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"sides": viewers}, f, ensure_ascii=False, separators=(",", ":"))
    return path

class HtmlReportRenderer:
    def render(self, result: Dict[str, Any], output_path: Optional[str] = None, title: str = "Kết quả chấm điểm động tác",
               viewers: Optional[Dict[str, Dict[str, Any]]] = None) -> str:
        """
        Ghi report.html đầy đủ (kèm trình xem 3D nếu có `viewers` {góc quay: dữ liệu}) ra output_path,
        trả về bản gọn không có dữ liệu 3D để nhúng vào bình luận điểm.
        """
        viewers = {s: v for s, v in (viewers or {}).items() if v}
        compact = self._document(result, title, {}, viewer_note=bool(viewers))
        if output_path:
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(self._document(result, title, viewers) if viewers else compact)
        return compact

    @staticmethod
    def _document(result: Dict[str, Any], title: str, viewers: Dict[str, Dict[str, Any]], viewer_note: bool = False) -> str:
        sides: Dict[str, Dict[str, Any]] = result.get("sides", {})
        score = result.get("score", 0.0)
        tabs = []
        for k, (side, res) in enumerate(sides.items()):
            sid = f"tab_{side}"
            tabs.append(
                f'<input type="radio" name="side" id="{sid}" {"checked" if k == 0 else ""}>'
                f'<label for="{sid}">{SIDE_LABELS.get(side, side)}</label>'
            )
        panels = "".join(
            f'<div class="panel" id="panel_{s}">'
            f'{_side_panel(s, r, _viewer_block(s, viewers[s]) if s in viewers else "")}</div>'
            for s, r in sides.items()
        )
        # CSS thuần: radio thứ k được chọn -> hiện panel thứ k
        show_rules = "".join(
            f"#tab_{s}:checked ~ .panels #panel_{s}{{display:block}}" for s in sides.keys()
        )
        script = ""
        if viewers:
            with open(_VIEWER_JS_PATH, encoding="utf-8") as f:
                script = f"<script>{f.read()}</script>"
        doc = (
            "<!doctype html><html lang='vi'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{html.escape(title)}</title><style>{_CSS}{show_rules}</style></head><body><div class=wrap>"
            f"<div class=card><h1>{html.escape(title)}</h1>"
            f"<div class='score {_score_class(score)}'>{score}/100</div>"
            f"<p>{html.escape(result.get('summary', ''))}</p>"
            f"<div class=muted>Thuật toán: DTW (cửa sổ Sakoe-Chiba) trên khoảng cách {html.escape(result.get('metric', 'PA-MPJPE'))}</div>"
            f"{_VIEWER_NOTE if viewer_note else ''}</div>"
            f"<div class=tabs>{''.join(tabs)}<div class=panels>{panels}</div></div>"
            f"</div>{script}</body></html>"
        )
        return doc
