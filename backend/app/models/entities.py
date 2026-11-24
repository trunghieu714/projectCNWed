import enum
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime, Enum, ForeignKey, Text, Boolean, UniqueConstraint
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

def get_utc_now():
    return datetime.now(timezone.utc)

class UserRole(str, enum.Enum):
    COACH = "coach"
    STUDENT = "student"
    ADMIN = "admin"

class SubmissionStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class EnrollmentStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    phonenumber = Column(String(20), unique=True, nullable=True, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=True)
    height = Column(Float, nullable=True)  # Chiều cao (cm) phục vụ chuẩn hóa Pose 3D
    avatar_url = Column(String(255), nullable=True)
    cover_image = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    role = Column(Enum(UserRole), default=UserRole.STUDENT, nullable=False)
    is_active = Column(Boolean, default=True)
    # Mã phiên đăng nhập hiện tại: đăng nhập máy khác làm token cũ hết hiệu lực (Slide 28 & 34)
    session_id = Column(String(64), nullable=True)
    device_uuid = Column(String(100), nullable=True)
    devtoken = Column(String(255), nullable=True)
    devtype = Column(String(10), nullable=True)
    created_at = Column(DateTime(timezone=True), default=get_utc_now)

    # Relationships
    exercises_created = relationship("Exercise", back_populates="coach")
    submissions = relationship("Submission", back_populates="student")
    course_taught = relationship("Course", back_populates="teacher", uselist=False)
    course_enrollments = relationship("CourseMember", back_populates="student")
    posts = relationship("SocialPost", back_populates="author")
    comments = relationship("Comment", back_populates="user")

class Course(Base):
    """
    Ràng buộc Slide 25 & 27:
    - Mỗi Giáo viên (teacher) chỉ quản lý DUY NHẤT 1 khóa học (teacher_id unique=True).
    - Tối đa 500 sinh viên.
    """
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    teacher_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    title = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    max_students = Column(Integer, default=500)
    created_at = Column(DateTime(timezone=True), default=get_utc_now)

    # Relationships
    teacher = relationship("User", back_populates="course_taught", foreign_keys=[teacher_id])
    exercises = relationship("Exercise", back_populates="course")
    members = relationship("CourseMember", back_populates="course")
    posts = relationship("SocialPost", back_populates="course")

class CourseMember(Base):
    """Bảng quan hệ nhiều-nhiều giữa Học viên và Khóa học."""
    __tablename__ = "course_members"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(Enum(EnrollmentStatus), default=EnrollmentStatus.APPROVED, nullable=False)
    joined_at = Column(DateTime(timezone=True), default=get_utc_now)

    # Relationships
    course = relationship("Course", back_populates="members")
    student = relationship("User", back_populates="course_enrollments")

class Exercise(Base):
    __tablename__ = "exercises"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=True)
    title = Column(String(150), nullable=False, index=True)
    category = Column(String(50), nullable=False)  # "military", "sword_dance", "artistic_dance"
    description = Column(Text, nullable=True)
    coach_video_url = Column(String(255), nullable=False)
    coach_pose_cache_url = Column(String(255), nullable=True)  # Cache kết quả trích xuất 3D pose HLV
    # Bài đăng của GV chính là bài tập (add_post Slide 40: exercise_id = id bài viết của GV)
    post_id = Column(Integer, ForeignKey("social_posts.id", use_alter=True, name="fk_exercise_post"), nullable=True, index=True)
    coach_video_right_url = Column(String(255), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=get_utc_now)

    # Relationships
    coach = relationship("User", back_populates="exercises_created", foreign_keys=[created_by])
    course = relationship("Course", back_populates="exercises")
    submissions = relationship("Submission", back_populates="exercise")
    posts = relationship("SocialPost", back_populates="exercise", foreign_keys="SocialPost.exercise_id")

class Submission(Base):
    __tablename__ = "submissions"

    id = Column(Integer, primary_key=True, index=True)
    exercise_id = Column(Integer, ForeignKey("exercises.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    student_video_url = Column(String(255), nullable=False)
    fused_video_url = Column(String(255), nullable=True)
    
    status = Column(Enum(SubmissionStatus), default=SubmissionStatus.PENDING, index=True)
    score = Column(Float, nullable=True)
    feedback_text = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    task_id = Column(String(100), nullable=True)  # Celery Task ID
    student_video_right_url = Column(String(255), nullable=True)
    # JSON kết quả chi tiết (điểm từng góc quay, warping path, danh sách lỗi)
    result_json = Column(Text, nullable=True)
    report_html_url = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=get_utc_now)
    updated_at = Column(DateTime(timezone=True), default=get_utc_now, onupdate=get_utc_now)

    # Relationships
    exercise = relationship("Exercise", back_populates="submissions")
    student = relationship("User", back_populates="submissions")
    post = relationship("SocialPost", back_populates="submission", uselist=False)

class SocialPost(Base):
    """
    Ràng buộc Slide 6 & 7:
    - Hỗ trợ tối đa 2 video (left_video_url, right_video_url).
    - Tự động liên kết course_id và exercise_id cho bài nộp.
    - Hỗ trợ thiết bị ghi hình (device_master, device_slave).
    """
    __tablename__ = "social_posts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=True)
    exercise_id = Column(Integer, ForeignKey("exercises.id"), nullable=True)
    submission_id = Column(Integer, ForeignKey("submissions.id"), nullable=True)
    
    content = Column(Text, nullable=False)
    video_left_url = Column(String(255), nullable=True)
    video_right_url = Column(String(255), nullable=True)
    video_fused_url = Column(String(255), nullable=True)
    device_master = Column(String(100), nullable=True)
    device_slave = Column(String(100), nullable=True)

    thumbnail_url = Column(String(255), nullable=True)
    edited_times = Column(Integer, default=0)

    likes_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=get_utc_now)
    updated_at = Column(DateTime(timezone=True), default=get_utc_now, onupdate=get_utc_now)

    # Relationships
    author = relationship("User", back_populates="posts", foreign_keys=[user_id])
    course = relationship("Course", back_populates="posts")
    exercise = relationship("Exercise", back_populates="posts", foreign_keys=[exercise_id])
    submission = relationship("Submission", back_populates="post")
    comments = relationship("Comment", back_populates="post", cascade="all, delete-orphan")
    likes = relationship("PostLike", cascade="all, delete-orphan")
    reports = relationship("PostReport", cascade="all, delete-orphan")

class Comment(Base):
    """
    Ràng buộc Slide 8, 42 & FAQ Q3:
    - Lưu trữ bình luận của học viên / người dùng.
    - Hỗ trợ Bot AI tự động comment điểm số (is_bot_evaluation=True).
    """
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("social_posts.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Nullable nếu là System Bot
    content = Column(Text, nullable=False)
    is_bot_evaluation = Column(Boolean, default=False)
    # set_comment: điểm số chấm được và xâu HTML chi tiết lỗi (đặc tả restful_api)
    score = Column(Float, nullable=True)
    detail_mistakes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=get_utc_now)

    # Relationships
    post = relationship("SocialPost", back_populates="comments")
    user = relationship("User", back_populates="comments")

class PostLike(Base):
    """Chỉ có một cảm xúc like duy nhất, mỗi người like một bài một lần (Slide 27)."""
    __tablename__ = "post_likes"
    __table_args__ = (UniqueConstraint("post_id", "user_id", name="uq_post_like"),)

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("social_posts.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=get_utc_now)

class PostReport(Base):
    """Bài viết bất kỳ đều có thể bị báo cáo (Slide 26)."""
    __tablename__ = "post_reports"
    __table_args__ = (UniqueConstraint("post_id", "user_id", name="uq_post_report"),)

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("social_posts.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    subject = Column(String(200), nullable=False)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=get_utc_now)

class UserBlock(Base):
    """Chặn / bỏ chặn không giới hạn thời gian (Slide 26)."""
    __tablename__ = "user_blocks"
    __table_args__ = (UniqueConstraint("blocker_id", "blocked_id", name="uq_user_block"),)

    id = Column(Integer, primary_key=True, index=True)
    blocker_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    blocked_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=get_utc_now)

class VerifyCode(Base):
    """Mã xác thực lưu trong DB thay vì RAM (không mất khi restart, dùng được nhiều worker)."""
    __tablename__ = "verify_codes"

    id = Column(Integer, primary_key=True, index=True)
    phonenumber = Column(String(20), nullable=False, index=True)
    code = Column(String(10), nullable=False)
    created_at = Column(DateTime(timezone=True), default=get_utc_now)

class SavedSearch(Base):
    __tablename__ = "saved_searches"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    keyword = Column(String(200), nullable=False)
    created_at = Column(DateTime(timezone=True), default=get_utc_now)

class Conversation(Base):
    """Chat 1-1, không có chat nhóm (Slide 27)."""
    __tablename__ = "conversations"
    __table_args__ = (UniqueConstraint("user_a_id", "user_b_id", name="uq_conversation_pair"),)

    id = Column(Integer, primary_key=True, index=True)
    user_a_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    user_b_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    # Mỗi bên có thể tự xóa cuộc hội thoại phía mình
    deleted_by_a = Column(Boolean, default=False)
    deleted_by_b = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=get_utc_now)
    updated_at = Column(DateTime(timezone=True), default=get_utc_now, onupdate=get_utc_now)

    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")

class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False, index=True)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=get_utc_now)

    conversation = relationship("Conversation", back_populates="messages")

class Notification(Base):
    """Lịch sử push: like, comment, bài mới, tin nhắn, đăng ký khóa học, đăng nhập máy khác..."""
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    type = Column(String(50), nullable=False)
    object_id = Column(Integer, nullable=True)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    title = Column(String(200), nullable=False)
    body = Column(Text, nullable=True)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=get_utc_now)

class PushSetting(Base):
    """
    Slide 31: cho phép tắt push, hoặc bật push với âm mặc định, hoặc âm có tiếng nói.
    sound_mode: 0 = tắt âm, 1 = âm mặc định, 2 = giọng nói thu âm.
    """
    __tablename__ = "push_settings"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    notification_on = Column(Boolean, default=True)
    sound_mode = Column(Integer, default=1)
    like_comment = Column(Boolean, default=True)
    new_post = Column(Boolean, default=True)
    message = Column(Boolean, default=True)
    enrollment = Column(Boolean, default=True)
    score = Column(Boolean, default=True)
