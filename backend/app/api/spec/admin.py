"""API trang quản trị (Slide 31): người quản trị thêm / sửa / xóa trực tiếp dữ liệu cần thiết."""
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import func, or_

from ...core.errors import ApiError, ok, param_invalid
from ...core.security import get_password_hash, verify_password
from ...core.text_rules import password_error
from ...models.entities import (Comment, Course, PostReport, SocialPost, Submission, User, UserRole)
from ...services.auth_service import AuthService, parse_role
from ...services.post_service import PostService
from ...services.serializers import iso, user_brief
from .params import Ctx, get_ctx

router = APIRouter(prefix="/admin")

def _admin(ctx: Ctx) -> User:
    user = ctx.user
    if user.role != UserRole.ADMIN:
        raise ApiError("1009", "Chỉ quản trị viên mới truy cập được.", 403)
    return user

@router.post("/login")
def login_admin(ctx: Ctx = Depends(get_ctx)):
    ident = ctx.p.str("username", required=True)
    user = ctx.db.query(User).filter(or_(User.username == ident, User.phonenumber == ident, User.email == ident)).first()
    if not user or user.role != UserRole.ADMIN or not verify_password(ctx.p.str("password", required=True), user.hashed_password):
        raise ApiError("9995", "Sai thông tin đăng nhập quản trị.", 401)
    token = AuthService(ctx.db)._new_session_token(user)
    return ok({"id": user.id, "username": user.username, "token": token, "role": user.role.value})

@router.post("/stats")
def stats(ctx: Ctx = Depends(get_ctx)):
    _admin(ctx)
    db = ctx.db
    return ok({
        "users": db.query(User).count(),
        "teachers": db.query(User).filter(User.role == UserRole.COACH).count(),
        "students": db.query(User).filter(User.role == UserRole.STUDENT).count(),
        "posts": db.query(SocialPost).count(), "courses": db.query(Course).count(),
        "submissions": db.query(Submission).count(), "reports": db.query(PostReport).count(),
        "avg_score": round(float(db.query(func.avg(Submission.score)).scalar() or 0), 1),
    })

@router.post("/users")
def list_users(ctx: Ctx = Depends(get_ctx)):
    _admin(ctx)
    index, count = ctx.p.page(50)
    q = ctx.db.query(User)
    kw = ctx.p.str("keyword")
    if kw:
        like = f"%{kw}%"
        q = q.filter(or_(User.username.ilike(like), User.phonenumber.ilike(like), User.full_name.ilike(like)))
    total = q.count()
    rows = q.order_by(User.id.desc()).offset(index).limit(count).all()
    return ok({"total": total, "users": [{**user_brief(u), "phonenumber": u.phonenumber, "is_active": u.is_active,
                                           "created": iso(u.created_at), "height": u.height} for u in rows]})

@router.post("/create_user")
def create_user(ctx: Ctx = Depends(get_ctx)):
    _admin(ctx)
    phone, pwd = ctx.p.str("phonenumber", required=True), ctx.p.str("password", required=True)
    err = password_error(pwd, phone)
    if err:
        raise param_invalid(err)
    if ctx.db.query(User).filter(User.phonenumber == phone).first():
        raise ApiError("9996", "Số điện thoại đã tồn tại.")
    user = User(username=ctx.p.str("username") or f"user_{phone}", phonenumber=phone, email=f"{phone}@local.vn",
                hashed_password=get_password_hash(pwd), role=parse_role(ctx.p.str("role")), is_active=True,
                full_name=ctx.p.str("full_name"))
    ctx.db.add(user)
    ctx.db.commit()
    return ok(user_brief(user))

@router.post("/update_user")
def update_user(ctx: Ctx = Depends(get_ctx)):
    admin = _admin(ctx)
    user = ctx.db.get(User, ctx.p.int("user_id", required=True))
    if not user:
        raise ApiError("9995", "Người dùng không tồn tại.", 404)
    if ctx.p.raw("is_active") is not None:
        if user.id == admin.id:
            raise param_invalid("Không thể tự khóa tài khoản quản trị.")
        user.is_active = ctx.p.flag("is_active")
        if not user.is_active:
            user.session_id = uuid.uuid4().hex
    if ctx.p.str("role"):
        user.role = UserRole.ADMIN if ctx.p.str("role").lower() == "admin" else parse_role(ctx.p.str("role"))
    for field in ("username", "full_name"):
        if ctx.p.str(field):
            setattr(user, field, ctx.p.str(field).strip())
    if ctx.p.str("password"):
        user.hashed_password = get_password_hash(ctx.p.str("password"))
    ctx.db.commit()
    return ok({**user_brief(user), "is_active": user.is_active})

@router.post("/reports")
def list_reports(ctx: Ctx = Depends(get_ctx)):
    _admin(ctx)
    index, count = ctx.p.page(50)
    rows = ctx.db.query(PostReport).order_by(PostReport.id.desc()).offset(index).limit(count).all()
    out = []
    for r in rows:
        post = ctx.db.get(SocialPost, r.post_id)
        out.append({"id": r.id, "post_id": r.post_id, "subject": r.subject, "details": r.details, "created": iso(r.created_at),
                    "reporter": user_brief(ctx.db.get(User, r.user_id)),
                    "post": {"described": post.content, "author": user_brief(post.author)} if post else None})
    return ok(out)

@router.post("/delete_report")
def delete_report(ctx: Ctx = Depends(get_ctx)):
    _admin(ctx)
    r = ctx.db.get(PostReport, ctx.p.int("id", required=True))
    if not r:
        raise ApiError("9994", "Không tìm thấy báo cáo.", 404)
    ctx.db.delete(r)
    ctx.db.commit()
    return ok(None)

@router.post("/delete_post")
def delete_post(ctx: Ctx = Depends(get_ctx)):
    admin = _admin(ctx)
    PostService(ctx.db).delete_post(admin, ctx.p.int("id", required=True))
    return ok(None)

@router.post("/delete_comment")
def delete_comment(ctx: Ctx = Depends(get_ctx)):
    _admin(ctx)
    c = ctx.db.get(Comment, ctx.p.int("id", required=True))
    if not c:
        raise ApiError("9994", "Không tìm thấy bình luận.", 404)
    ctx.db.delete(c)
    ctx.db.commit()
    return ok(None)

@router.post("/courses")
def list_courses(ctx: Ctx = Depends(get_ctx)):
    _admin(ctx)
    rows = ctx.db.query(Course).order_by(Course.id.asc()).all()
    return ok([{"id": c.teacher_id, "internal_id": c.id, "title": c.title, "description": c.description,
                "max_students": c.max_students, "teacher": user_brief(c.teacher)} for c in rows])

@router.post("/update_course")
def update_course(ctx: Ctx = Depends(get_ctx)):
    _admin(ctx)
    c = ctx.db.query(Course).filter(Course.teacher_id == ctx.p.int("course_id", required=True)).first()
    if not c:
        raise ApiError("9994", "Khóa học không tồn tại.", 404)
    if ctx.p.str("title"):
        c.title = ctx.p.str("title", max_len=150)
    if ctx.p.raw("description") is not None:
        c.description = ctx.p.str("description")
    if ctx.p.raw("max_students") is not None:
        c.max_students = min(500, ctx.p.int("max_students", minimum=1))
    ctx.db.commit()
    return ok({"id": c.teacher_id, "title": c.title, "max_students": c.max_students})
