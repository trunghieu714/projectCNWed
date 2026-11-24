from typing import Dict, Any
from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from ....core.database import get_db
from ....schemas.user import (
    UserCreate, UserLogin, Token, UserResponse,
    UserSignupByPhone, VerifyCodeRequest, ChangeInfoAfterSignupRequest, UserInfoUpdate
)
from ....schemas.response import ApiResponse, ErrorCodes
from ....services.auth_service import AuthService
from ...deps import get_current_user
from ....models.entities import User

router = APIRouter()

# 1. Đăng ký & Đăng nhập truyền thống (giữ tương thích)
@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    service = AuthService(db)
    return service.register(user_in)

@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    service = AuthService(db)
    login_data = UserLogin(
        username_or_email=form_data.username,
        password=form_data.password
    )
    return service.login(login_data)

@router.get("/me", response_model=UserResponse)
def get_current_user_profile(current_user: User = Depends(get_current_user)):
    return current_user

# 2. Cập nhật thông tin người dùng (API set_user_info chuẩn Slide 3 & PUT /me)
@router.post("/set_user_info", response_model=ApiResponse[UserResponse])
@router.put("/me", response_model=ApiResponse[UserResponse])
def set_user_info(
    info_in: UserInfoUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    API set_user_info (Chuẩn Slide 3 danh sách 40 API):
    Cho phép người dùng sửa đổi username, full_name, chiều cao (height) và avatar.
    """
    from ....repositories.user_repository import UserRepository
    repo = UserRepository(db)
    updated = repo.update_profile(
        user_id=current_user.id,
        username=info_in.username,
        full_name=info_in.full_name,
        height=info_in.height,
        avatar_url=info_in.avatar_url
    )
    return ApiResponse(code=ErrorCodes.OK, message="Cập nhật thông tin thành công.", data=updated)

# 3. Các API theo đặc tả Slide 41-45 (Tuần 2)
@router.post("/signup", response_model=ApiResponse[Dict[str, Any]], status_code=status.HTTP_201_CREATED)
def signup_by_phone(signup_in: UserSignupByPhone, db: Session = Depends(get_db)):
    """Đăng ký tài khoản bằng số điện thoại (Chuẩn Slide 41)."""
    service = AuthService(db)
    result = service.signup_by_phone(signup_in)
    return ApiResponse(code=result["code"], message=result["message"], data=result["data"])

@router.post("/check_verify_code", response_model=ApiResponse[Dict[str, Any]])
def check_verify_code(verify_in: VerifyCodeRequest, db: Session = Depends(get_db)):
    """Xác nhận mã xác thực và cấp mã phiên đăng nhập token (Chuẩn Slide 8 Tuần 2)."""
    service = AuthService(db)
    result = service.check_verify_code(verify_in)
    return ApiResponse(code=result["code"], message=result["message"], data=result["data"])

@router.post("/change_info_after_signup", response_model=ApiResponse[Dict[str, Any]])
def change_info_after_signup(
    info_in: ChangeInfoAfterSignupRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Cập nhật username hiển thị, chiều cao (cm), ảnh đại diện (Chuẩn Slide 14 Tuần 2)."""
    service = AuthService(db)
    result = service.change_info_after_signup(current_user.id, info_in)
    return ApiResponse(code=result["code"], message=result["message"], data=result["data"])
