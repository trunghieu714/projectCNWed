# Hướng dẫn chạy thử & chuẩn bị bảo vệ – MotionAI Coach

Docker đã có sẵn dữ liệu mẫu: HLV `coach_hoang` có khóa học, học viên `student_nam` **đã được duyệt** vào khóa đó
(mật khẩu cả hai: `Password123`, theo `backend/seed_data.py`).

---

## 1. Khi nào cần chép URL Colab mới?

Không phải chỉ lúc bảo vệ: **mỗi khi muốn chấm bằng AI thật (GVHMR)** thì Colab phải đang chạy.

- URL tunnel và khóa API **chỉ đổi khi chạy lại notebook** (runtime mới, hoặc chạy lại Bước 2 và Bước 8).
  Colab còn chạy thì URL giữ nguyên.
- Colab miễn phí tự ngắt sau ~90 phút không thao tác, tối đa ~12 giờ. Hôm bảo vệ nên mở Colab
  **trước 30–40 phút** và chạy hết Bước 1 → 8 của `colab/MotionAI_Colab_GPU_Server.ipynb`.
- Mỗi lần có URL mới, dán 2 dòng mà Bước 8 in ra vào file **`.env` ở thư mục gốc** (Docker đọc file này)
  và `backend/.env` (khi chạy backend không qua Docker):
  ```
  AI_REMOTE_URL=https://....trycloudflare.com
  AI_REMOTE_API_KEY=....
  ```
  rồi áp dụng:
  ```bash
  docker compose up -d
  ```
- Colab tắt thì hệ thống vẫn chạy nhưng rơi về **pose giả lập (mock)** – vẫn ra điểm nhưng không có ý nghĩa.

Link mở notebook (luôn mở từ link này, không dùng bản "Sao chép vào Drive"):
```
https://colab.research.google.com/github/trunghieu714/projectCNWed/blob/main/colab/MotionAI_Colab_GPU_Server.ipynb
```

---

## 2. Video mẫu để chạy thử (miễn phí, Mixkit)

| Vai trò | Link tải | Nội dung |
|---|---|---|
| **HLV** | https://assets.mixkit.co/videos/21273/21273-720.mp4 | Nam squat tại nhà, toàn thân, 15,7 giây |
| **Học viên (làm đúng)** | https://assets.mixkit.co/videos/52106/52106-720.mp4 | Nữ squat có tạ ấm, 12,3 giây |
| **Học viên (sai động tác)** | https://assets.mixkit.co/videos/752/752-720.mp4 | Nữ squat rồi ném bóng, 14,5 giây |

Mẹo kiểm tra:
- Học viên nộp **chính video của HLV** → điểm phải gần **100**.
- Nộp video ném bóng → điểm phải **thấp hơn rõ** so với video squat.

Nguồn: [Mixkit – Squat Stock Videos](https://mixkit.co/free-stock-video/squat/) (Mixkit Free License).

---

## 3. Các bước chạy thử

### Bước 0 – Chuẩn bị
1. Nếu còn, xóa thư mục `backend/storage/outputs/sub_1/` (kết quả giả còn sót từ lần kiểm tra).
2. Cho Docker dùng code mới (có nút tải zip):
   ```bash
   docker compose up -d --build
   ```
3. Colab đang chạy, `.env` đã có `AI_REMOTE_URL` và `AI_REMOTE_API_KEY` mới.

### Bước 1 – HLV đăng bài mẫu (http://localhost:3000)
1. Đăng nhập `coach_hoang` / `Password123`.
2. Bấm **"+ Đăng Bài Mẫu (HLV)"**, chọn video HLV, ghi mô tả, đăng.
3. Server gửi video lên Colab để trích pose HLV (~**5–6 phút**). Pose được lưu lại, lần chấm sau không chạy lại.

### Bước 2 – Học viên nộp bài
1. Đăng xuất, đăng nhập `student_nam` / `Password123`.
2. Vào **Cộng Đồng** → bài của HLV → bấm **"Nộp bài"** (vị trí nút Chia sẻ) → chọn video học viên
   (1 video, hoặc 2 video trái/phải) → nộp.
3. Bài đăng hiện ngay; hệ thống chấm ngầm ~**5–6 phút mỗi video**.

### Bước 3 – Xem kết quả
1. Tải lại trang: dưới bài nộp có bình luận **🤖 AI Auto-Scorer** kèm điểm.
2. **"Xem chi tiết lỗi"** → báo cáo HTML gọn (tab Bên Trái / Bên Phải).
   **"Xem 3D"** → **khung xương 3D HLV – HV hiện ngay dưới bình luận điểm** (bấm lần nữa để ẩn).
3. Trang kết quả bài nộp (`/submissions/<id>`): ngay dưới 2 video HLV / học viên có mục
   **"Khung xương 3D – so sánh HLV & học viên"** **đi theo video**: bấm "Phát đồng bộ" hoặc tua video thì khung xương
   nhảy tới đúng thời điểm đó – vừa xem video vừa thấy khớp nào sai.
   - Kéo chuột để xoay góc nhìn, lăn chuột để phóng to; chọn "Chồng lên nhau" / "Cạnh nhau" / "Chỉ HLV" / "Chỉ học viên".
   - HLV màu xanh dương, học viên màu xanh lá, **khớp lệch quá ngưỡng tô đỏ**; dòng dưới khung ghi khớp lệch nhiều nhất.
   - Học viên đã được căn khớp về HLV (Procrustes) đúng như khi tính điểm PA-MPJPE.
   - Bài chấm trước khi có tính năng này: chạy `docker exec skill_backend python refresh_reports.py` để tạo dữ liệu 3D.
4. **"Tải kết quả (.zip)"** → `report.html` + `result.json`. Trong `result.json`, `pose_source` có
   **`remote:gvhmr`** = chấm bằng AI thật; `mock` = Colab chưa kết nối.
5. Học viên nhận thông báo "Đã có kết quả chấm điểm".

Theo dõi Colab đang xử lý tới đâu (tạo ô mới trên Colab):
```python
!tail -20 /content/pose_server.log
```

---

## 4. Mẹo cho buổi bảo vệ

- **Đăng bài mẫu của HLV từ trước**, lúc demo chỉ còn chờ chấm bài học viên.
- Dùng video ngắn **10–15 giây** để chấm nhanh.
- Slide yêu cầu demo bằng **video quay bằng điện thoại thật** (ít nhất 2 điện thoại, có 3G/4G) và laptop/PC có GPU
  (Colab được chấp nhận theo FAQ Q5). Video Mixkit chỉ để chạy thử.
- Báo cáo: bản cứng nộp hôm bảo vệ, bản mềm trước 3 ngày; ghi rõ phân công và link GitHub.
- Bảo vệ thử buổi 13, bảo vệ chính buổi 14–16, đi đủ thành viên.

---

## 5. Khi Colab gặp lỗi

| Hiện tượng | Cách xử lý |
|---|---|
| Bước 4 báo "Too many users have viewed or downloaded" | Thêm lối tắt thư mục checkpoint chính thức vào "Drive của tôi" (Sắp xếp → Thêm lối tắt), chạy lại ô kết nối Drive với `force_remount=True` rồi chạy lại Bước 4; hoặc đợi vài giờ; hoặc đặt `ALLOW_HF_MIRROR = True` |
| Bước 5 chạy lâu | Kiểm tra `!tail -5 /content/gvhmr.log`, `!nvidia-smi --query-gpu=memory.used --format=csv,noheader`, `!curl -s http://127.0.0.1:8000/api/v1/health` |
| Tab Colab đang mở là bản cũ | Đóng tab, mở lại link notebook ở mục 1 |
| Runtime bị lỗi thư viện | Thời gian chạy → Ngắt kết nối và xoá thời gian chạy → chạy lại từ Bước 1 |

Checkpoint GVHMR (~5 GB) và 2 file mô hình cơ thể (`SMPLX_NEUTRAL.npz`, `SMPL_NEUTRAL.pkl`) nằm trong
`MyDrive/GVHMR_checkpoints/` – chỉ tải một lần.
