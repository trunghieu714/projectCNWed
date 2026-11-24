from typing import List, Optional
from sqlalchemy.orm import Session
from ..models.entities import Course, CourseMember, EnrollmentStatus, User

class CourseRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, teacher_id: int, title: str, description: Optional[str] = None, max_students: int = 500) -> Course:
        # Kiểm tra giáo viên đã có khóa học chưa (Ràng buộc: 1 GV = 1 khóa)
        existing = self.db.query(Course).filter(Course.teacher_id == teacher_id).first()
        if existing:
            raise ValueError(f"Giáo viên ID {teacher_id} đã có một khóa học trực tuyến. Mỗi giáo viên chỉ được quản lý 01 khóa học.")

        course = Course(
            teacher_id=teacher_id,
            title=title,
            description=description,
            max_students=min(max_students, 500)
        )
        self.db.add(course)
        self.db.commit()
        self.db.refresh(course)
        return course

    def get_by_id(self, course_id: int) -> Optional[Course]:
        return self.db.query(Course).filter(Course.id == course_id).first()

    def get_by_teacher(self, teacher_id: int) -> Optional[Course]:
        return self.db.query(Course).filter(Course.teacher_id == teacher_id).first()

    def get_all(self, skip: int = 0, limit: int = 50) -> List[Course]:
        return self.db.query(Course).offset(skip).limit(limit).all()

    def enroll_student(self, course_id: int, student_id: int) -> CourseMember:
        course = self.get_by_id(course_id)
        if not course:
            raise ValueError("Không tìm thấy khóa học.")

        # Đếm số lượng học viên hiện tại (tối đa 500)
        current_count = self.db.query(CourseMember).filter(
            CourseMember.course_id == course_id,
            CourseMember.status == EnrollmentStatus.APPROVED
        ).count()

        if current_count >= course.max_students:
            raise ValueError(f"Khóa học đã đạt giới hạn tối đa {course.max_students} học viên.")

        # Kiểm tra đã đăng ký chưa
        existing = self.db.query(CourseMember).filter(
            CourseMember.course_id == course_id,
            CourseMember.student_id == student_id
        ).first()

        if existing:
            return existing

        member = CourseMember(
            course_id=course_id,
            student_id=student_id,
            status=EnrollmentStatus.APPROVED
        )
        self.db.add(member)
        self.db.commit()
        self.db.refresh(member)
        return member

    def get_student_courses(self, student_id: int) -> List[Course]:
        memberships = self.db.query(CourseMember).filter(
            CourseMember.student_id == student_id,
            CourseMember.status == EnrollmentStatus.APPROVED
        ).all()
        return [m.course for m in memberships if m.course]
