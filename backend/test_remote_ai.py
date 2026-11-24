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
            print(f"  [+] Chế độ            : {data.get('backend')} (nguồn {data.get('source')})")
        else:
            print(f"  [-] Thất bại: HTTP {resp.status_code} - {resp.text}")
            sys.exit(1)
    except Exception as e:
        print(f"  [-] Lỗi kết nối tới {target_url}: {e}")
        print("  [-] Vui lòng kiểm tra lại notebook Colab và URL tunnel.")
        sys.exit(1)

    # 2. Extract pose check (POST /extract)
    # Ưu tiên dùng video quay người thật thay vì video người que vẽ nét
    import glob
    real_vids = [
        os.path.join(current_dir, "storage", "coach_samples", "coach_1_fused_output.mp4"),
        os.path.join(current_dir, "storage", "uploads", "post_u2_left_7283996808e2.mp4"),
    ]
    sample_video = None
    for rv in real_vids:
        if os.path.exists(rv):
            sample_video = rv
            break
    if not sample_video:
        all_vids = glob.glob(os.path.join(current_dir, "storage", "**", "*.mp4"), recursive=True)
        for v in all_vids:
            if "coach_sample.mp4" not in v and os.path.getsize(v) > 100000:
                sample_video = v
                break

    if not sample_video or not os.path.exists(sample_video):
        print("\n[2/2] Bỏ qua kiểm tra trích xuất video vì không tìm thấy file mp4 mẫu.")
        print("\n[+] Health check thành công! Server sẵn sàng nhận video.")
        return

    print(f"\n[2/2] Gửi video mẫu để trích xuất Pose 3D (POST /extract)...")
    print(f"    Tệp: {os.path.basename(sample_video)} ({round(os.path.getsize(sample_video)/1024, 1)} KB)")
    print(f"    Đang xử lý trên GPU từ xa, vui lòng đợi...")

    # Gửi đúng giao thức backend dùng: POST /jobs rồi hỏi trạng thái, kèm X-API-Key
    from ai_engine.models.remote_estimator import RemotePoseEstimator
    from ai_engine.pose_io import PoseNotAvailable
    est = RemotePoseEstimator(target_url, timeout=settings.AI_REMOTE_TIMEOUT, api_key=settings.AI_REMOTE_API_KEY,
                              poll_interval=settings.AI_REMOTE_POLL_INTERVAL)
    try:
        t0 = time.time()
        pose = est.extract_poses(sample_video)
        dt = round(time.time() - t0, 2)
        print(f"  [+] TRÍCH XUẤT THÀNH CÔNG! (Tổng thời gian: {dt}s)")
        print(f"  [+] Khớp 3D                  : {pose['joints_3d'].shape[0]} frames x {pose['joints_3d'].shape[1]} khớp")
        print(f"  [+] FPS video                : {pose['fps']}")
        print(f"  [+] Nguồn xử lý              : {pose['source']}")
        print("\n" + "=" * 65)
        print("[SUCCESS] Pipeline AI từ xa hoạt động!")
        print("=" * 65)
    except PoseNotAvailable as e:
        print(f"  [-] Thất bại: {e}")
        if "401" in str(e):
            print("  [-] Sai khóa: đặt AI_REMOTE_API_KEY trong .env bằng POSE_SERVER_KEY mà notebook Colab in ra.")

if __name__ == "__main__":
    main()
