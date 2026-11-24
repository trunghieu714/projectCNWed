from tests.helpers import make_video_bytes
import io
import pytest
from fastapi.testclient import TestClient
from main import app
from app.core.database import Base, engine, SessionLocal
from app.models.entities import User, UserRole, Exercise, Course
from app.core.security import create_access_token

client = TestClient(app)

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield

import time

def test_auth_signup_by_phone_flow():
    phone_unique = f"09{int(time.time() * 100) % 100000000:08d}"
    # 1. Đăng ký bằng số điện thoại
    resp = client.post("/api/v1/auth/signup", json={
        "phonenumber": phone_unique,
        "password": "strongPassword123"
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["code"] == "1000"
    assert "verify_code" in data["data"]
    v_code = data["data"]["verify_code"]

    # 2. Xác thực mã verify code
    resp_v = client.post("/api/v1/auth/check_verify_code", json={
        "phonenumber": phone_unique,
        "verify_code": v_code
    })
    assert resp_v.status_code == 200
    token_data = resp_v.json()["data"]
    assert "token" in token_data
    token = token_data["token"]

    # 3. Đổi thông tin sau đăng ký (username, height, avatar)
    headers = {"Authorization": f"Bearer {token}"}
    unique_username = f"nam_{int(time.time() * 1000) % 1000000}"
    resp_info = client.post("/api/v1/auth/change_info_after_signup", json={
        "username": unique_username,
        "height": 178.0,
        "avatar_url": "https://cdn.local/avatar.png"
    }, headers=headers)
    assert resp_info.status_code == 200
    assert resp_info.json()["data"]["username"] == unique_username
    assert resp_info.json()["data"]["height"] == 178.0

def test_course_api_lifecycle():
    db = SessionLocal()
    # Tạo coach và student
    coach = db.query(User).filter(User.username == "coach_course_test").first()
    if not coach:
        coach = User(username="coach_course_test", email="c_course@test.com", hashed_password="pw", role=UserRole.COACH)
        db.add(coach)
        db.commit()
        db.refresh(coach)
    coach_token = create_access_token(subject=coach.id, role=coach.role.value)
    
    student = db.query(User).filter(User.username == "student_course_test").first()
    if not student:
        student = User(username="student_course_test", email="s_course@test.com", hashed_password="pw", role=UserRole.STUDENT)
        db.add(student)
        db.commit()
        db.refresh(student)
    student_token = create_access_token(subject=student.id, role=student.role.value)
    db.close()

    # Giáo viên tạo khóa học
    headers_coach = {"Authorization": f"Bearer {coach_token}"}
    resp_c = client.post("/api/v1/courses/", json={
        "title": "Khóa Huấn Luyện Điều Lệnh Đặc Biệt",
        "description": "Dành cho khóa K65",
        "max_students": 100
    }, headers=headers_coach)
    # Có thể là 201 hoặc 400 nếu đã tạo
    assert resp_c.status_code in [201, 400]
    
    # Học viên xem danh sách khóa học
    resp_get = client.get("/api/v1/courses/")
    assert resp_get.status_code == 200
    assert resp_get.json()["code"] == "1000"
    courses = resp_get.json()["data"]
    assert len(courses) >= 1

    # Học viên đăng ký khóa học
    course_id = courses[0]["id"]
    headers_student = {"Authorization": f"Bearer {student_token}"}
    resp_enroll = client.post(f"/api/v1/courses/{course_id}/enroll", headers=headers_student)
    assert resp_enroll.status_code in [200, 400]

def test_add_post_with_video_and_auto_comment():
    db = SessionLocal()
    student = db.query(User).filter(User.username == "student_post_tester").first()
    if not student:
        student = User(username="student_post_tester", email="s_post@test.com", hashed_password="pw", role=UserRole.STUDENT)
        db.add(student)
        db.commit()
        db.refresh(student)
    student_token = create_access_token(subject=student.id, role=student.role.value)

    # Đảm bảo có ít nhất 1 bài tập
    exercise = db.query(Exercise).first()
    if not exercise:
        exercise = Exercise(
            title="Động tác Chào Chuẩn",
            category="military",
            coach_video_url="storage/coach_samples/coach_sample.mp4",
            created_by=student.id
        )
        db.add(exercise)
        db.commit()
        db.refresh(exercise)
    exercise_id = exercise.id
    # Bài tập thuộc khóa học: HV phải được GV duyệt vào khóa mới nộp bài được (Slide 6)
    if exercise.course_id:
        from app.models.entities import CourseMember, EnrollmentStatus
        if not db.query(CourseMember).filter(CourseMember.course_id == exercise.course_id,
                                             CourseMember.student_id == student.id).first():
            db.add(CourseMember(course_id=exercise.course_id, student_id=student.id, status=EnrollmentStatus.APPROVED))
            db.commit()
    db.close()

    headers = {"Authorization": f"Bearer {student_token}"}

    # Giả lập file video tải lên
    fake_video = io.BytesIO(make_video_bytes(seed=3))
    files = {
        "left_video": ("student_left.mp4", fake_video, "video/mp4")
    }
    data = {
        "described": "Nộp bài tập điều lệnh buổi 1",
        "course_id": "1",
        "exercise_id": str(exercise_id)
    }

    # Gọi API add_post (Slide 6)
    resp = client.post("/api/v1/posts/add_post", data=data, files=files, headers=headers)
    assert resp.status_code == 201
    post_res = resp.json()
    assert post_res["code"] == "1000"
    post_id = post_res["data"]["id"]
    assert "#course_1" in post_res["data"]["content"]
    assert f"#exercise_{exercise_id}" in post_res["data"]["content"]

    # Nếu Celery đang chạy bất đồng bộ với Redis, thực thi hoàn tất tác vụ
    if post_res["data"]["submission_id"]:
        from app.workers.video_tasks import process_submission_core
        process_submission_core(post_res["data"]["submission_id"])

    # Kiểm tra danh sách comment của post xem AI Bot đã tự động comment chưa (FAQ Q3)
    resp_cmt = client.get(f"/api/v1/posts/{post_id}/comments")
    assert resp_cmt.status_code == 200
    comments = resp_cmt.json()["data"]
    assert len(comments) >= 1
    # Comment của bot có is_bot_evaluation = True
    bot_comment = [c for c in comments if c["is_bot_evaluation"] is True]
    assert len(bot_comment) >= 1
    assert "KẾT QUẢ ĐÁNH GIÁ ĐỘNG TÁC TỰ ĐỘNG" in bot_comment[0]["content"]
