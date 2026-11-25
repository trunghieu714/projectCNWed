"""
Cập nhật các kết quả chấm đã có lên trình xem khung xương 3D mới nhất (dữ liệu chấm không đổi):
- thay JavaScript trình xem trong report.html (khi sửa ai_engine/visualizers/skeleton_viewer.js);
- tạo skeleton3d.json (trang web vẽ khung xương 3D cạnh video) cho bài chấm trước khi có file này.

    cd backend
    python refresh_reports.py                 # mặc định storage/outputs
    docker exec skill_backend python refresh_reports.py
"""
import glob
import os
import sys

from ai_engine.visualizers.html_report import extract_viewer_data, refresh_viewer, write_skeleton_json

def main(root: str = "storage/outputs") -> None:
    reports = skeletons = 0
    for path in sorted(glob.glob(os.path.join(root, "sub_*", "report.html"))):
        with open(path, encoding="utf-8") as f:
            doc = f.read()
        new = refresh_viewer(doc)
        if new is not None and new != doc:
            with open(path, "w", encoding="utf-8") as f:
                f.write(new)
            reports += 1
        skeleton = os.path.join(os.path.dirname(path), "skeleton3d.json")
        if not os.path.exists(skeleton) and write_skeleton_json(skeleton, extract_viewer_data(doc)):
            skeletons += 1
            print("Đã tạo", skeleton)
    print(f"Xong: cập nhật JS cho {reports} báo cáo, tạo {skeletons} file skeleton3d.json.")

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "storage/outputs")
