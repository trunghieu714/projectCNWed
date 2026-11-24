from tests.helpers import make_video_bytes
import os
import io
import pytest
from fastapi.testclient import TestClient
from main import app
from app.core.database import Base, engine, init_db

client = TestClient(app)

@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    init_db()
    yield

def test_full_api_workflow():
    # 1. Test Root Endpoint
    res_root = client.get("/")
    assert res_root.status_code == 200
    assert res_root.json()["status"] == "online"

    # 2. Đăng ký tài khoản Huấn luyện viên (Coach)
    coach_payload = {
        "username": "coach_hoang",
        "email": "coach_hoang@example.com",
        "password": "Password123!",
        "full_name": "Hoàng Minh",
        "role": "coach"
    }
    res_reg_coach = client.post("/api/v1/auth/register", json=coach_payload)
    assert res_reg_coach.status_code in [201, 400]  # 400 nếu đã tồn tại từ lần chạy trước

    # 3. Đăng nhập HLV để lấy JWT Token
    res_login_coach = client.post(
        "/api/v1/auth/login",
        data={"username": "coach_hoang", "password": "Password123!"}
    )
    assert res_login_coach.status_code == 200
    coach_token = res_login_coach.json()["access_token"]
    coach_headers = {"Authorization": f"Bearer {coach_token}"}

    # 4. Kiểm tra Endpoint /auth/me
    res_me = client.get("/api/v1/auth/me", headers=coach_headers)
    assert res_me.status_code == 200
    assert res_me.json()["username"] == "coach_hoang"
    assert res_me.json()["role"] == "coach"

    # 5. Huấn luyện viên tạo bài tập mới
    fake_video_content = make_video_bytes(seed=1)
    video_file = ("sample_coach.mp4", io.BytesIO(fake_video_content), "video/mp4")
    res_create_ex = client.post(
        "/api/v1/exercises/",
        headers=coach_headers,
        data={
            "title": "Động tác Chào Điều lệnh Chuẩn",
            "category": "military",
            "description": "Hướng dẫn thực hiện động tác đứng nghiêm và đưa tay chào đúng góc độ."
        },
        files={"file": video_file}
    )
    assert res_create_ex.status_code == 201
    exercise_id = res_create_ex.json()["id"]

    # 6. Lấy danh sách bài tập (Public API)
    res_ex_list = client.get("/api/v1/exercises/")
    assert res_ex_list.status_code == 200
    assert any(ex["id"] == exercise_id for ex in res_ex_list.json())

    # 7. Đăng ký & Đăng nhập tài khoản Học viên (Student)
    student_payload = {
        "username": "student_nam",
        "email": "student_nam@example.com",
        "password": "Password123!",
        "full_name": "Lê Văn Nam",
        "role": "student"
    }
    client.post("/api/v1/auth/register", json=student_payload)
    res_login_student = client.post(
        "/api/v1/auth/login",
        data={"username": "student_nam", "password": "Password123!"}
    )
    assert res_login_student.status_code == 200
    student_token = res_login_student.json()["access_token"]
    student_headers = {"Authorization": f"Bearer {student_token}"}

    # 8. Học viên nộp video bài tập để chấm điểm
    student_video_content = make_video_bytes(seed=2)
    student_file = ("student_submission.mp4", io.BytesIO(student_video_content), "video/mp4")
    res_submit = client.post(
        "/api/v1/submissions/submit",
        headers=student_headers,
        data={"exercise_id": exercise_id},
        files={"file": student_file}
    )
    assert res_submit.status_code == 202
    sub_data = res_submit.json()
    submission_id = sub_data["id"]
    assert sub_data["status"] in ["PENDING", "PROCESSING", "COMPLETED"]

    # 9. Lấy chi tiết bài nộp
    res_sub_detail = client.get(f"/api/v1/submissions/{submission_id}", headers=student_headers)
    assert res_sub_detail.status_code == 200
    assert res_sub_detail.json()["id"] == submission_id

    # 10. Tạo bài viết chia sẻ trên Mạng Xã Hội Luyện Tập
    res_post = client.post(
        "/api/v1/posts/",
        headers=student_headers,
        json={
            "content": "Mình vừa hoàn thành bài tập Điều lệnh chào chuẩn! Cảm ơn HLV đã hướng dẫn.",
            "submission_id": submission_id
        }
    )
    assert res_post.status_code == 201
    post_id = res_post.json()["id"]

    # 11. Xem Bản Tin Cộng Đồng
    res_feed = client.get("/api/v1/posts/")
    assert res_feed.status_code == 200
    assert any(p["id"] == post_id for p in res_feed.json())

    # 12. Thả tim bài viết
    res_like = client.post(f"/api/v1/posts/{post_id}/like", headers=coach_headers)
    assert res_like.status_code == 200
    assert res_like.json()["likes_count"] >= 1
