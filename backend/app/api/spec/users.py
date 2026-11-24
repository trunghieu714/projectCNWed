"""Nhóm API người dùng & khóa học: get_user_info, set_user_info, get_list_blocks, set_block,
set_request_course, get_requested_enrollment, set_approve_enrollment, get_list_students,
get_list_courses_of_student, get_list_courses, set_course_info."""
from fastapi import APIRouter, Depends

from ...core.errors import ApiError, no_access, ok, param_invalid
from ...core.text_rules import username_error
from ...models.entities import Course, CourseMember, EnrollmentStatus, SocialPost, User, UserRole
from ...services.relationship_service import CourseService, RelationshipService
from ...services.serializers import iso, role_label, user_brief
from ...services.video_service import save_image_upload
from .params import Ctx, get_ctx

router = APIRouter()

def _course_dict(db, course: Course, viewer=None):
    svc = CourseService(db)
    status = None
    if viewer:
        m = svc.membership(course.id, viewer.id)
        status = m.status.value if m else None
    return {
        "id": course.teacher_id, "course_id": course.teacher_id, "internal_id": course.id,
        "title": course.title, "description": course.description, "max_students": course.max_students,
        "students_count": svc.approved_count(course.id), "teacher": user_brief(course.teacher),
        "created": iso(course.created_at), "my_status": status,
    }

@router.post("/get_user_info")
def get_user_info(ctx: Ctx = Depends(get_ctx)):
    viewer = ctx.optional_user
    user_id = ctx.p.int("user_id") or (viewer.id if viewer else None)
    if not user_id:
        raise ApiError("1002", "Thiếu tham số user_id.")
    user = ctx.db.get(User, user_id)
    if not user:
        raise ApiError("9995", "Người dùng không tồn tại.", 404)
    rel = RelationshipService(ctx.db)
    if viewer and viewer.id != user.id and rel.is_blocked_between(viewer.id, user.id):
        raise no_access("Hai người đã chặn nhau nên không xem được trang của nhau.")
    courses = CourseService(ctx.db)
    if user.role == UserRole.COACH:
        course = ctx.db.query(Course).filter(Course.teacher_id == user.id).first()
        followed = courses.approved_count(course.id) if course else 0
    else:
        followed = len(courses.approved_course_ids(user.id))
    is_self = bool(viewer and viewer.id == user.id)
    is_related = False
    if viewer and not is_self:
        pairs = [(user, viewer), (viewer, user)]
        for teacher, student in pairs:
            if teacher.role == UserRole.COACH:
                c = ctx.db.query(Course).filter(Course.teacher_id == teacher.id).first()
                if c and courses.is_approved_member(c.id, student.id):
                    is_related = True
    data = {
        "id": user.id, "username": user.username, "full_name": user.full_name, "avatar": user.avatar_url,
        "cover_image": user.cover_image, "description": user.description, "height": user.height,
        "url": f"/profile/{user.id}", "created": iso(user.created_at), "status": "active" if user.is_active else "inactive",
        "role": user.role.value, "role_label": role_label(user),
        "listing": ctx.db.query(SocialPost).filter(SocialPost.user_id == user.id).count(),
        "followed": followed, "is_related": is_related,
        "is_blocked": bool(viewer and rel.has_blocked(viewer.id, user.id)),
        "online": bool(user.session_id),
    }
    if is_self:
        data.update({"email": user.email, "phonenumber": user.phonenumber})
    return ok(data)

@router.post("/set_user_info")
def set_user_info(ctx: Ctx = Depends(get_ctx)):
    user = ctx.user
    p = ctx.p
    username, full_name, description = p.str("username"), p.str("full_name", max_len=100), p.str("description", max_len=1000)
    height = p.float("height")
    avatar, cover = p.file("avatar"), p.file("cover_image")
    if not any([username, full_name, description, height, avatar, cover]):
        raise ApiError("1002", "Cần tối thiểu một thông tin để cập nhật.")
    if username:
        err = username_error(username, user.phonenumber)
        if err:
            raise param_invalid(err)
        other = ctx.db.query(User).filter(User.username == username.strip(), User.id != user.id).first()
        if other:
            raise ApiError("9996", "Tên người dùng đã được sử dụng.")
        user.username = username.strip()
    if height is not None:
        if not (50 <= height <= 250):
            raise param_invalid("Chiều cao không hợp lệ (50 - 250 cm).")
        user.height = height
    if full_name is not None:
        user.full_name = full_name.strip()
    if description is not None:
        user.description = description.strip()
    if avatar:
        user.avatar_url = save_image_upload(avatar, f"avatar_u{user.id}")
    if cover:
        user.cover_image = save_image_upload(cover, f"cover_u{user.id}")
    ctx.db.commit()
    return ok({"id": user.id, "username": user.username, "avatar": user.avatar_url, "cover_image": user.cover_image,
               "full_name": user.full_name, "height": user.height})

@router.post("/get_list_blocks")
def get_list_blocks(ctx: Ctx = Depends(get_ctx)):
    index, count = ctx.p.page()
    total, users = RelationshipService(ctx.db).list_blocks(ctx.user, index, count)
    return ok({"total": total, "users": [user_brief(u) for u in users if u]})

@router.post("/set_block")
@router.post("/blocks")
def set_block(ctx: Ctx = Depends(get_ctx)):
    """Input: token, user_id, type (0: block, 1: unblock)."""
    block_type = ctx.p.int("type", default=0)
    if block_type not in (0, 1):
        raise param_invalid("type chỉ nhận 0 (chặn) hoặc 1 (bỏ chặn).")
    RelationshipService(ctx.db).set_block(ctx.user, ctx.p.int("user_id", required=True), unblock=block_type == 1)
    return ok(None, "Đã bỏ chặn." if block_type == 1 else "Đã chặn người dùng.")

# ---------------------------------------------------------------------------------------------- khóa học
@router.post("/get_list_courses")
def get_list_courses(ctx: Ctx = Depends(get_ctx)):
    index, count = ctx.p.page()
    viewer = ctx.optional_user
    hidden = RelationshipService(ctx.db).hidden_user_ids(viewer.id if viewer else None)
    q = ctx.db.query(Course)
    if hidden:
        q = q.filter(~Course.teacher_id.in_(hidden))
    return ok([_course_dict(ctx.db, c, viewer) for c in q.order_by(Course.id.asc()).offset(index).limit(count).all()])

@router.post("/set_course_info")
def set_course_info(ctx: Ctx = Depends(get_ctx)):
    teacher = ctx.require_role(UserRole.COACH)
    course = CourseService(ctx.db).ensure_course(teacher)
    title = ctx.p.str("title", max_len=150)
    if title:
        course.title = title.strip()
    desc = ctx.p.str("description")
    if desc is not None:
        course.description = desc.strip()
    ctx.db.commit()
    return ok(_course_dict(ctx.db, course, teacher))

@router.post("/set_request_course")
def set_request_course(ctx: Ctx = Depends(get_ctx)):
    """HV gửi yêu cầu tham gia khóa học. Input: token, course_id (= id giáo viên)."""
    svc = CourseService(ctx.db)
    course = svc.get_by_spec_id(ctx.p.int("course_id", required=True))
    if not course:
        raise ApiError("9994", "Khóa học không tồn tại.", 404)
    member = svc.request(ctx.user, course)
    return ok({"course_id": course.teacher_id, "status": member.status.value}, "Đã gửi yêu cầu, chờ giáo viên duyệt.")

@router.post("/get_requested_enrollment")
def get_requested_enrollment(ctx: Ctx = Depends(get_ctx)):
    teacher = ctx.user
    target = teacher
    if ctx.p.int("user_id") and teacher.role == UserRole.ADMIN:
        target = ctx.db.get(User, ctx.p.int("user_id")) or teacher
    if target.role != UserRole.COACH:
        raise no_access("Chỉ giáo viên mới có danh sách yêu cầu đăng ký.")
    index, count = ctx.p.page()
    rows = CourseService(ctx.db).list_requests(target, index, count)
    return ok([{**user_brief(m.student), "request": "enroll", "status": m.status.value, "created": iso(m.joined_at),
                "url": f"/profile/{m.student_id}"} for m in rows])

@router.post("/set_approve_enrollment")
def set_approve_enrollment(ctx: Ctx = Depends(get_ctx)):
    """Input: token, user_id (học viên), is_accept (1: chấp nhận, 0: từ chối)."""
    member = CourseService(ctx.db).approve(ctx.user, ctx.p.int("user_id", required=True), ctx.p.flag("is_accept", True))
    return ok({"user_id": member.student_id, "status": member.status.value})

@router.post("/get_list_students")
def get_list_students(ctx: Ctx = Depends(get_ctx)):
    svc = CourseService(ctx.db)
    viewer = ctx.optional_user
    course_id = ctx.p.int("course_id") or (viewer.id if viewer and viewer.role == UserRole.COACH else None)
    course = svc.get_by_spec_id(course_id)
    if not course:
        raise ApiError("1002", "Thiếu tham số course_id.")
    index, count = ctx.p.page(50)
    rows = svc.list_students(course, index, count)
    return ok({"total": svc.approved_count(course.id),
               "students": [{**user_brief(m.student), "joined": iso(m.joined_at)} for m in rows]})

@router.post("/get_list_courses_of_student")
def get_list_courses_of_student(ctx: Ctx = Depends(get_ctx)):
    viewer = ctx.user
    student_id = ctx.p.int("user_id") or viewer.id
    rows = CourseService(ctx.db).courses_of_student(student_id)
    if student_id != viewer.id:
        rows = [(c, m) for c, m in rows if m.status == EnrollmentStatus.APPROVED]
    return ok([{**_course_dict(ctx.db, c), "status": m.status.value} for c, m in rows])
