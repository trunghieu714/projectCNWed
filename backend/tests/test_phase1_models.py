import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.entities import Base, User, UserRole, Course, CourseMember, Exercise, SocialPost, Comment, EnrollmentStatus
from app.repositories.course_repository import CourseRepository
from app.repositories.comment_repository import CommentRepository
from app.repositories.social_repository import SocialRepository
from app.repositories.user_repository import UserRepository

# SQLite in-memory test database
TEST_DB_URL = "sqlite:///:memory:"
test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

@pytest.fixture(scope="function")
def db():
    Base.metadata.create_all(bind=test_engine)
    session = TestingSessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=test_engine)

def test_user_phone_and_height(db):
    user_repo = UserRepository(db)
    user = user_repo.create(
        username="student_098",
        email="s098@local.vn",
        password="password123",
        phonenumber="0987654321",
        height=175.5,
        role=UserRole.STUDENT
    )
    assert user.id is not None
    assert user.phonenumber == "0987654321"
    assert user.height == 175.5
    
    found = user_repo.get_by_phone("0987654321")
    assert found is not None
    assert found.username == "student_098"

def test_course_one_teacher_one_course_constraint(db):
    user_repo = UserRepository(db)
    teacher = user_repo.create(
        username="teacher_minh",
        email="minh@hust.edu.vn",
        password="secretpassword",
        role=UserRole.COACH
    )

    course_repo = CourseRepository(db)
    # 1. Tạo khóa học đầu tiên -> Thành công
    c1 = course_repo.create(
        teacher_id=teacher.id,
        title="Lớp Huấn Luyện Điều Lệnh K65",
        description="Huấn luyện các động tác điều lệnh cơ bản",
        max_students=500
    )
    assert c1.id is not None
    assert c1.teacher_id == teacher.id

    # 2. Tạo khóa học thứ hai cho cùng 1 GV -> Bị chặn
    with pytest.raises(ValueError, match="Mỗi giáo viên chỉ được quản lý 01 khóa học"):
        course_repo.create(
            teacher_id=teacher.id,
            title="Lớp Huấn Luyện Kiếm Đạo",
            description="Lớp thứ hai không được phép"
        )

def test_course_enrollment_and_limit(db):
    user_repo = UserRepository(db)
    teacher = user_repo.create(username="teacher_tuan", email="tuan@hust.edu.vn", password="pw", role=UserRole.COACH)
    student1 = user_repo.create(username="student_nam", email="nam@hust.edu.vn", password="pw", role=UserRole.STUDENT)
    student2 = user_repo.create(username="student_lan", email="lan@hust.edu.vn", password="pw", role=UserRole.STUDENT)

    course_repo = CourseRepository(db)
    course = course_repo.create(teacher_id=teacher.id, title="Lớp Thể Dục 1", max_students=1)

    # Học viên 1 tham gia -> Thành công
    m1 = course_repo.enroll_student(course.id, student1.id)
    assert m1.id is not None
    assert m1.status == EnrollmentStatus.APPROVED

    # Học viên 2 tham gia -> Bị chặn do vượt quá max_students
    with pytest.raises(ValueError, match="đã đạt giới hạn tối đa"):
        course_repo.enroll_student(course.id, student2.id)

def test_social_post_two_videos_and_comments(db):
    user_repo = UserRepository(db)
    student = user_repo.create(username="student_anh", email="anh@hust.edu.vn", password="pw", role=UserRole.STUDENT)

    social_repo = SocialRepository(db)
    post = social_repo.create(
        user_id=student.id,
        content="Bài nộp môn Điều lệnh #course_1 #exercise_2",
        video_left_url="storage/uploads/left_cam.mp4",
        video_right_url="storage/uploads/right_cam.mp4",
        course_id=1,
        exercise_id=2
    )
    assert post.id is not None
    assert post.video_left_url == "storage/uploads/left_cam.mp4"
    assert post.video_right_url == "storage/uploads/right_cam.mp4"

    # Thêm comment chấm điểm từ AI Bot
    comment_repo = CommentRepository(db)
    bot_cmt = comment_repo.create(
        post_id=post.id,
        content="Điểm số: 88.5/100 (Rất tốt). Góc khuỷu tay chuẩn 90 độ.",
        user_id=None,
        is_bot_evaluation=True
    )
    assert bot_cmt.id is not None
    assert bot_cmt.is_bot_evaluation is True

    feed = social_repo.get_feed()
    assert len(feed) >= 1
    # Check that comments are loaded
    p0 = [f for f in feed if f["id"] == post.id][0]
    assert len(p0["comments"]) == 1
    assert p0["comments"][0].is_bot_evaluation is True
