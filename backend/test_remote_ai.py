"""
Script kiểm thử kết nối tới Server AI GPU từ xa (Google Colab / PC khác).
Cách chạy:
    cd backend
    python test_remote_ai.py
    # Hoặc chỉ định URL trực tiếp:
    python test_remote_ai.py https://xxxx.ngrok-free.app
"""
import os
import sys
import time

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

import httpx
from app.core.config import settings

def main():
    target_url = sys.argv[1] if len(sys.argv) > 1 else settings.AI_REMOTE_URL
    if not target_url:
        print("[!] LỖI: Chưa cấu hình AI_REMOTE_URL trong file .env hoặc chưa truyền tham số URL.")
        print("    Ví dụ: python test_remote_ai.py https://abc-xyz.trycloudflare.com")
        sys.exit(1)

    target_url = target_url.rstrip("/")
    print("=" * 65)
    print(f"[*] ĐANG KIỂM TRA KẾT NỐI SERVER AI TỪ XA:")
    print(f"    URL: {target_url}")
    print("=" * 65)

    # 1. Health check (GET /)
    print("\n[1/2] Gửi yêu cầu Health Check (GET /)...")
    try:
        t0 = time.time()
        resp = httpx.get(f"{target_url}/", timeout=15)
        dt = round(time.time() - t0, 2)
        if resp.status_code == 200:
            data = resp.json()
            print(f"  [+] THÀNH CÔNG! (Status: {resp.status_code}, Phản hồi: {dt}s)")
            print(f"  [+] Trạng thái server : {data.get('status')}")
            print(f"  [+] Nguồn Pose        : {data.get('source')}")
            print(f"  [+] Lệnh trích xuất   : {data.get('command')}")
        else:
            print(f"  [-] Thất bại: HTTP {resp.status_code} - {resp.text}")
            sys.exit(1)
    except Exception as e:
        print(f"  [-] Lỗi kết nối tới {target_url}: {e}")
        print("  [-] Vui lòng kiểm tra lại notebook Colab và URL tunnel.")
        sys.exit(1)

    # 2. Extract pose check (POST /extract)
    sample_video = os.path.join(current_dir, "storage", "coach_samples", "coach_sample.mp4")
    if not os.path.exists(sample_video):
        # Fallback thử tìm trong uploads
        import glob
        vids = glob.glob(os.path.join(current_dir, "storage", "**", "*.mp4"), recursive=True)
        sample_video = vids[0] if vids else None

    if not sample_video or not os.path.exists(sample_video):
        print("\n[2/2] Bỏ qua kiểm tra trích xuất video vì không tìm thấy file mp4 mẫu.")
        print("\n[+] Health check thành công! Server sẵn sàng nhận video.")
        return

    print(f"\n[2/2] Gửi video mẫu để trích xuất Pose 3D (POST /extract)...")
    print(f"    Tệp: {os.path.basename(sample_video)} ({round(os.path.getsize(sample_video)/1024, 1)} KB)")
    print(f"    Đang xử lý trên GPU từ xa, vui lòng đợi...")

    try:
        t0 = time.time()
        with open(sample_video, "rb") as f:
            files = {"file": (os.path.basename(sample_video), f, "video/mp4")}
            resp = httpx.post(f"{target_url}/extract", files=files, timeout=300)
        dt = round(time.time() - t0, 2)

        if resp.status_code == 200:
            result = resp.json()
            joints = result.get("joints_3d", [])
            print(f"  [+] TRÍCH XUẤT THÀNH CÔNG! (Tổng thời gian: {dt}s)")
            print(f"  [+] Số khung hình trích xuất : {len(joints)} frames")
            print(f"  [+] FPS video                : {result.get('fps')}")
            print(f"  [+] Nguồn xử lý              : {result.get('source')}")
            print(f"  [+] Thời gian GPU xử lý      : {result.get('seconds')}s")
            print("\n" + "=" * 65)
            print("[SUCCESS] CHÚC MỪNG! Pipeline AI từ xa hoạt động hoàn hảo 100%!")
            print("=" * 65)
        else:
            print(f"  [-] Thất bại: HTTP {resp.status_code} - {resp.text}")
    except Exception as e:
        print(f"  [-] Lỗi trong quá trình trích xuất: {e}")

if __name__ == "__main__":
    main()
