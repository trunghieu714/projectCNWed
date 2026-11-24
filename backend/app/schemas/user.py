from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional
from datetime import datetime
from ..models.entities import UserRole

class UserBase(BaseModel):
    username: str
    email: Optional[EmailStr] = None
    phonenumber: Optional[str] = None
    full_name: Optional[str] = None
    height: Optional[float] = None
    avatar_url: Optional[str] = None
    role: UserRole = UserRole.STUDENT

class UserCreate(UserBase):
    password: str

class UserSignupByPhone(BaseModel):
    """Đăng ký theo số điện thoại chuẩn Slide 41-45."""
    phonenumber: str
    password: str

class VerifyCodeRequest(BaseModel):
    phonenumber: str
    verify_code: str

class ChangeInfoAfterSignupRequest(BaseModel):
    username: Optional[str] = None
    height: Optional[float] = None
    avatar_url: Optional[str] = None

class UserInfoUpdate(BaseModel):
    """Cập nhật thông tin người dùng (API set_user_info chuẩn Slide 3)."""
    username: Optional[str] = None
    full_name: Optional[str] = None
    height: Optional[float] = None
    avatar_url: Optional[str] = None

class UserLogin(BaseModel):
    username_or_email: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user_id: int
    username: str
    phonenumber: Optional[str] = None

class UserResponse(UserBase):
    id: int
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
