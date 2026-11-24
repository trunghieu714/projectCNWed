"""
Tạo dữ liệu mẫu để demo: 1 quản trị viên, 1 giáo viên (kèm khóa học + 1 bài tập mẫu), 1 học viên đã
được duyệt vào khóa học. Mật khẩu theo quy tắc đề tài: không chứa ký tự đặc biệt.

    python seed_data.py
"""
import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from app.core.database import SessionLocal, init_db
from app.core.security import get_password_hash
from app.models.entities import Course, CourseMember, EnrollmentStatus, Exercise, SocialPost, User, UserRole

PASSWORD = "Password123"
ACCOUNTS = [
    ("admin", "0900000000", "Quản trị viên", UserRole.ADMIN, 170.0),
    ("coach_hoang", "0901234567", "Đại Úy Hoàng Minh Tuấn", UserRole.COACH, 176.0),
    ("student_nam", "0987654321", "Nguyễn Văn Nam", UserRole.STUDENT, 174.5),
]

def _sample_video(path: str, seconds: int = 12) -> None:
    """Video mẫu (hình người que chuyển động) khi chưa có video quay thật của GV."""
    import cv2
    import numpy as np
    os.makedirs(os.path.dirname(path), exist_ok=True)
    out = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), 25, (640, 480))
    for i in range(seconds * 25):
        t = i / 25.0
        frame = np.full((480, 640, 3), 245, np.uint8)
        cx, cy = 320, 200
        arm = np.deg2rad(60 * np.sin(t * 2))
        cv2.circle(frame, (cx, cy - 70), 25, (40, 40, 40), 3)
        cv2.line(frame, (cx, cy - 45), (cx, cy + 80), (40, 40, 40), 4)
        for side in (-1, 1):
            hand = (int(cx + side * 90 * np.cos(arm)), int(cy - 90 * np.sin(arm) * side))
            cv2.line(frame, (cx, cy - 20), hand, (30, 90, 200), 4)
            cv2.line(frame, (cx, cy + 80), (cx + side * 40, cy + 190), (30, 140, 60), 4)
        cv2.putText(frame, "Video mau - hay thay bang video quay that", (110, 450), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (90, 90, 90), 1)
        out.write(frame)
    out.release()

def seed_all():
    print("Khởi tạo cấu trúc bảng trong Database...")
    init_db()
    db = SessionLocal()
    try:
        users = {}
        for username, phone, name, role, height in ACCOUNTS:
            user = db.query(User).filter(User.username == username).first()
            if not user:
                user = User(username=username, email=f"{username}@local.vn", phonenumber=phone, full_name=name,
                            height=height, role=role, is_active=True, hashed_password=get_password_hash(PASSWORD))
                db.add(user)
                db.commit()
                db.refresh(user)
                print(f"-> Đã tạo {role.value}: {username} / SĐT {phone} / mật khẩu {PASSWORD}")
            users[role] = user
        coach, student = users[UserRole.COACH], users[UserRole.STUDENT]

        course = db.query(Course).filter(Course.teacher_id == coach.id).first()
        if not course:
            course = Course(teacher_id=coach.id, title="Lớp Huấn Luyện Điều Lệnh Quân Sự K65", max_students=500,
                            description="Rèn luyện các động tác điều lệnh cơ bản: chào chuẩn, đi đều, dừng lại.")
            db.add(course)
            db.commit()
            db.refresh(course)
            print(f"-> Đã tạo khóa học: {course.title}")

        if not db.query(CourseMember).filter(CourseMember.course_id == course.id, CourseMember.student_id == student.id).first():
            db.add(CourseMember(course_id=course.id, student_id=student.id, status=EnrollmentStatus.APPROVED))
            db.commit()
            print("-> Đã duyệt học viên vào khóa học.")

        if not db.query(Exercise).filter(Exercise.created_by == coach.id, Exercise.post_id.isnot(None)).first():
            video = "storage/coach_samples/coach_sample.mp4"
            if not os.path.exists(video):
                _sample_video(video)
            post = SocialPost(user_id=coach.id, course_id=course.id, video_left_url="/" + video,
                              content="Động tác Chào Điều lệnh Chuẩn: giơ tay phải theo đường ngắn nhất, ngón tay duỗi thẳng.")
            db.add(post)
            db.commit()
            db.refresh(post)
            ex = Exercise(course_id=course.id, title="Động tác Chào Điều lệnh Chuẩn", category="military",
                          description=post.content, coach_video_url="/" + video, created_by=coach.id, post_id=post.id)
            db.add(ex)
            db.commit()
            post.exercise_id = ex.id
            post.content = f"#course_{coach.id} #exercise_{post.id} {post.content}"
            db.commit()
            print(f"-> Đã tạo bài tập mẫu (bài viết #{post.id}) của giáo viên.")

        print("\n✅ Khởi tạo dữ liệu mẫu thành công!")
    except Exception as e:
        db.rollback()
        print(f"❌ Lỗi khi khởi tạo dữ liệu: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed_all()
