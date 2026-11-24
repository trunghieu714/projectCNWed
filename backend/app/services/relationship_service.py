"""Chặn người dùng (Slide 26) và đăng ký / duyệt khóa học (Slide 25, 27; API set_request_course...)."""
from typing import List, Optional, Set, Tuple

from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..core.errors import ApiError, no_access, param_invalid
from ..models.entities import Course, CourseMember, EnrollmentStatus, User, UserBlock, UserRole
from .notification_service import NotificationService

class RelationshipService:
    def __init__(self, db: Session):
        self.db = db

    def has_blocked(self, blocker_id: int, blocked_id: int) -> bool:
        return self.db.query(UserBlock).filter(
            UserBlock.blocker_id == blocker_id, UserBlock.blocked_id == blocked_id
        ).first() is not None

    def is_blocked_between(self, a: Optional[int], b: Optional[int]) -> bool:
        if not a or not b or a == b:
            return False
        return self.has_blocked(a, b) or self.has_blocked(b, a)

    def hidden_user_ids(self, user_id: Optional[int]) -> Set[int]:
        """Những người mà user_id không được thấy bài/trang (chặn theo cả 2 chiều)."""
        if not user_id:
            return set()
        rows = self.db.query(UserBlock).filter(
            or_(UserBlock.blocker_id == user_id, UserBlock.blocked_id == user_id)
        ).all()
        return {r.blocked_id if r.blocker_id == user_id else r.blocker_id for r in rows}

    def blocked_by_me(self, user_id: Optional[int]) -> Set[int]:
        if not user_id:
            return set()
        return {r.blocked_id for r in self.db.query(UserBlock).filter(UserBlock.blocker_id == user_id).all()}

    def set_block(self, user: User, target_id: int, unblock: bool) -> None:
        if target_id == user.id:
            raise param_invalid("Không thể tự chặn chính mình.")
        target = self.db.get(User, target_id)
        if not target:
            raise ApiError("9995", "Người dùng không tồn tại.", 404)
        existing = self.db.query(UserBlock).filter(
            UserBlock.blocker_id == user.id, UserBlock.blocked_id == target_id
        ).first()
        if unblock:
            if not existing:
                raise ApiError("1010", "Bạn chưa chặn người dùng này.")
            self.db.delete(existing)
            self.db.commit()
            return
        if existing:
            raise ApiError("1010", "Bạn đã chặn người dùng này trước đó.")
        self.db.add(UserBlock(blocker_id=user.id, blocked_id=target_id))
        # Chặn giữa HV và GV khiến HV không còn là người học của khóa đó (Slide 26)
        pairs = [(user, target), (target, user)]
        for teacher, student in pairs:
            if teacher.role == UserRole.COACH:
                course = self.db.query(Course).filter(Course.teacher_id == teacher.id).first()
                if course:
                    self.db.query(CourseMember).filter(
                        CourseMember.course_id == course.id, CourseMember.student_id == student.id
                    ).delete()
        self.db.commit()

    def list_blocks(self, user: User, index: int, count: int) -> Tuple[int, List[User]]:
        q = self.db.query(UserBlock).filter(UserBlock.blocker_id == user.id).order_by(UserBlock.created_at.desc())
        total = q.count()
        rows = q.offset(index).limit(count).all()
        return total, [self.db.get(User, r.blocked_id) for r in rows]

class CourseService:
    def __init__(self, db: Session):
        self.db = db

    def ensure_course(self, teacher: User) -> Course:
        """Mỗi GV có đúng 1 khóa học (Slide 27); tạo tự động khi GV hoạt động lần đầu."""
        course = self.db.query(Course).filter(Course.teacher_id == teacher.id).first()
        if not course:
            course = Course(teacher_id=teacher.id, title=f"Khóa học của {teacher.full_name or teacher.username}", max_students=500)
            self.db.add(course)
            self.db.commit()
            self.db.refresh(course)
        return course

    def get_by_spec_id(self, course_id: Optional[int]) -> Optional[Course]:
        """Theo đặc tả, course_id trùng với id của giáo viên; vẫn chấp nhận id nội bộ của khóa học."""
        if not course_id:
            return None
        course = self.db.query(Course).filter(Course.teacher_id == course_id).first()
        if course:
            return course
        teacher = self.db.get(User, course_id)
        if teacher and teacher.role == UserRole.COACH:
            return self.ensure_course(teacher)
        return self.db.get(Course, course_id)

    def membership(self, course_id: int, student_id: int) -> Optional[CourseMember]:
        return self.db.query(CourseMember).filter(
            CourseMember.course_id == course_id, CourseMember.student_id == student_id
        ).first()

    def is_approved_member(self, course_id: int, student_id: int) -> bool:
        m = self.membership(course_id, student_id)
        return bool(m and m.status == EnrollmentStatus.APPROVED)

    def approved_count(self, course_id: int) -> int:
        return self.db.query(CourseMember).filter(
            CourseMember.course_id == course_id, CourseMember.status == EnrollmentStatus.APPROVED
        ).count()

    def approved_course_ids(self, student_id: Optional[int]) -> Set[int]:
        if not student_id:
            return set()
        rows = self.db.query(CourseMember).filter(
            CourseMember.student_id == student_id, CourseMember.status == EnrollmentStatus.APPROVED
        ).all()
        return {r.course_id for r in rows}

    def request(self, student: User, course: Course) -> CourseMember:
        from .relationship_service import RelationshipService
        if student.role != UserRole.STUDENT:
            raise no_access("Chỉ học viên mới đăng ký khóa học.")
        if RelationshipService(self.db).is_blocked_between(student.id, course.teacher_id):
            raise no_access("Không thể đăng ký khóa học của người đã chặn / bị chặn.")
        existing = self.membership(course.id, student.id)
        if existing and existing.status in (EnrollmentStatus.APPROVED, EnrollmentStatus.PENDING):
            raise ApiError("1010", "Bạn đã gửi yêu cầu hoặc đã tham gia khóa học này.")
        if self.approved_count(course.id) >= course.max_students:
            raise ApiError("1004", f"Khóa học đã đủ tối đa {course.max_students} học viên.")
        if existing:
            existing.status = EnrollmentStatus.PENDING
            member = existing
        else:
            member = CourseMember(course_id=course.id, student_id=student.id, status=EnrollmentStatus.PENDING)
            self.db.add(member)
        self.db.commit()
        self.db.refresh(member)
        NotificationService(self.db).notify(
            course.teacher_id, "enrollment_request", "Yêu cầu đăng ký khóa học",
            f"{student.full_name or student.username} muốn đăng ký khóa học của bạn.", object_id=student.id, actor_id=student.id,
        )
        return member

    def list_requests(self, teacher: User, index: int, count: int) -> List[CourseMember]:
        course = self.ensure_course(teacher)
        return (self.db.query(CourseMember)
                .filter(CourseMember.course_id == course.id, CourseMember.status == EnrollmentStatus.PENDING)
                .order_by(CourseMember.joined_at.desc()).offset(index).limit(count).all())

    def approve(self, teacher: User, student_id: int, accept: bool) -> CourseMember:
        if teacher.role != UserRole.COACH:
            raise no_access("Chỉ giáo viên mới duyệt yêu cầu đăng ký.")
        course = self.ensure_course(teacher)
        member = self.membership(course.id, student_id)
        if not member or member.status != EnrollmentStatus.PENDING:
            raise ApiError("9994", "Không có yêu cầu đăng ký đang chờ của học viên này.", 404)
        if accept and self.approved_count(course.id) >= course.max_students:
            raise ApiError("1004", f"Khóa học đã đủ tối đa {course.max_students} học viên.")
        member.status = EnrollmentStatus.APPROVED if accept else EnrollmentStatus.REJECTED
        self.db.commit()
        self.db.refresh(member)
        NotificationService(self.db).notify(
            student_id, "enrollment_result", "Kết quả đăng ký khóa học",
            f"Yêu cầu tham gia '{course.title}' đã được {'chấp nhận' if accept else 'từ chối'}.",
            object_id=course.teacher_id, actor_id=teacher.id,
        )
        return member

    def list_students(self, course: Course, index: int, count: int) -> List[CourseMember]:
        return (self.db.query(CourseMember)
                .filter(CourseMember.course_id == course.id, CourseMember.status == EnrollmentStatus.APPROVED)
                .order_by(CourseMember.joined_at.asc()).offset(index).limit(count).all())

    def courses_of_student(self, student_id: int) -> List[Tuple[Course, CourseMember]]:
        rows = self.db.query(CourseMember).filter(CourseMember.student_id == student_id).all()
        return [(r.course, r) for r in rows if r.course]
