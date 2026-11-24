"""Nhóm API đăng ký / đăng nhập: login, logout, signup, get_verify_code, check_verify_code,
change_info_after_signup, change_password, set_devtoken, check_new_version."""
from fastapi import APIRouter, Depends

from ...core.config import settings
from ...core.errors import ok
from ...schemas.user import ChangeInfoAfterSignupRequest, UserSignupByPhone, VerifyCodeRequest
from ...services.auth_service import AuthService
from ...services.video_service import save_image_upload
from .params import Ctx, get_ctx

router = APIRouter()

@router.post("/login")
def login(ctx: Ctx = Depends(get_ctx)):
    """Input: phonenumber, password, uuid. Output: id, username, token, avatar (-1: cần đổi tên & ảnh), role."""
    data = AuthService(ctx.db).login_by_phone(
        ctx.p.str("phonenumber", required=True), ctx.p.str("password", required=True), ctx.p.str("uuid"))
    return ok(data)

@router.post("/logout")
def logout(ctx: Ctx = Depends(get_ctx)):
    AuthService(ctx.db).logout(ctx.user)
    return ok(None)

@router.post("/signup")
def signup(ctx: Ctx = Depends(get_ctx)):
    """Input: phonenumber, password, uuid, role (GV | HV)."""
    res = AuthService(ctx.db).signup_by_phone(
        UserSignupByPhone(phonenumber=ctx.p.str("phonenumber", required=True), password=ctx.p.str("password", required=True)),
        role=ctx.p.str("role"), device_uuid=ctx.p.str("uuid"),
    )
    return ok(res["data"], res["message"])

@router.post("/get_verify_code")
def get_verify_code(ctx: Ctx = Depends(get_ctx)):
    res = AuthService(ctx.db).get_verify_code(ctx.p.str("phonenumber", required=True))
    return ok(res["data"])

@router.post("/check_verify_code")
def check_verify_code(ctx: Ctx = Depends(get_ctx)):
    code = ctx.p.str("code_verify") or ctx.p.str("verify_code") or ctx.p.str("code")
    res = AuthService(ctx.db).check_verify_code(
        VerifyCodeRequest(phonenumber=ctx.p.str("phonenumber", required=True), verify_code=code or ""))
    return ok(res["data"], res["message"])

@router.post("/change_info_after_signup")
def change_info_after_signup(ctx: Ctx = Depends(get_ctx)):
    """Input: token, username, avatar (file, không bắt buộc), height (cm)."""
    user = ctx.user
    avatar = ctx.p.file("avatar")
    avatar_url = save_image_upload(avatar, f"avatar_u{user.id}") if avatar else None
    res = AuthService(ctx.db).change_info_after_signup(user.id, ChangeInfoAfterSignupRequest(
        username=ctx.p.str("username", required=True), height=ctx.p.float("height"), avatar_url=avatar_url))
    return ok(res["data"], res["message"])

@router.post("/change_password")
def change_password(ctx: Ctx = Depends(get_ctx)):
    AuthService(ctx.db).change_password(ctx.user, ctx.p.str("password", required=True), ctx.p.str("new_password", required=True))
    return ok(None, "Đổi mật khẩu thành công.")

@router.post("/set_devtoken")
def set_devtoken(ctx: Ctx = Depends(get_ctx)):
    AuthService(ctx.db).set_devtoken(ctx.user, ctx.p.str("devtype"), ctx.p.str("devtoken", required=True))
    return ok(None)

@router.post("/check_new_version")
def check_new_version(ctx: Ctx = Depends(get_ctx)):
    current = ctx.p.str("last_update") or ctx.p.str("version") or "0"

    def parse(v: str):
        try:
            return tuple(int(x) for x in v.split("."))
        except ValueError:
            return (0,)
    latest, required = settings.CLIENT_LATEST_VERSION, settings.CLIENT_REQUIRED_VERSION
    user = ctx.optional_user
    return ok({
        "version": {"version": latest, "require": 1 if parse(current) < parse(required) else 0,
                    "url": "/"},
        "user": {"id": user.id, "active": 1 if user.is_active else 0} if user else None,
        "badge": 0,
        "now": settings.APP_VERSION,
    })
