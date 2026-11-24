import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from ..repositories.user_repository import UserRepository
from ..schemas.user import UserCreate, UserLogin, Token, UserSignupByPhone, VerifyCodeRequest, ChangeInfoAfterSignupRequest
from ..schemas.response import ErrorCodes
from ..core.errors import ApiError
from ..core.security import verify_password, create_access_token, get_password_hash
from ..core.text_rules import PHONE_INVALID_MSG, is_valid_phone, password_error, username_error
from ..models.entities import User, UserRole, VerifyCode
from .notification_service import NotificationService
from .serializers import iso, role_label

VERIFY_CODE_COOLDOWN_SECONDS = 30

def parse_role(raw: Optional[str]) -> UserRole:
    value = (raw or "").strip().lower()
    if value in ("gv", "coach", "teacher", "giaovien", "giáo viên", "1"):
        return UserRole.COACH
    if value in ("hv", "hs", "student", "hocvien", "học viên", "0", ""):
        return UserRole.STUDENT
    raise ApiError(ErrorCodes.PARAMETER_VALUE_INVALID, "Loại tài khoản chỉ nhận GV hoặc HV.")

class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = UserRepository(db)

    # ------------------------------------------------------------------------------------------
    # Mã xác thực (lưu DB, không gửi SMS thật - Slide 28 tuần 2)
    # ------------------------------------------------------------------------------------------
    def _issue_code(self, phone: str) -> str:
        code = f"{random.randint(0, 999999):06d}"
        self.db.query(VerifyCode).filter(VerifyCode.phonenumber == phone).delete()
        self.db.add(VerifyCode(phonenumber=phone, code=code))
        self.db.commit()
        return code

    def _new_session_token(self, user: User, device_uuid: Optional[str] = None) -> str:
        old_session, old_device = user.session_id, user.device_uuid
        user.session_id = uuid.uuid4().hex
        if device_uuid:
            user.device_uuid = device_uuid
        self.db.commit()
        if old_session and device_uuid and old_device and old_device != device_uuid:
            NotificationService(self.db).notify(
                user.id, "login_other_device", "Đăng nhập trên thiết bị khác",
                "Tài khoản của bạn vừa được đăng nhập trên một thiết bị khác.",
            )
        return create_access_token(subject=user.id, role=user.role.value, session_id=user.session_id)

    # ------------------------------------------------------------------------------------------
    # API v1 (giữ tương thích)
    # ------------------------------------------------------------------------------------------
    def register(self, user_in: UserCreate) -> Token:
        if self.repo.get_by_username(user_in.username):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tên người dùng đã tồn tại.")
        if user_in.email and self.repo.get_by_email(user_in.email):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email đã được sử dụng.")
        user = self.repo.create(
            username=user_in.username, email=user_in.email, password=user_in.password,
            full_name=user_in.full_name, role=user_in.role,
        )
        token = create_access_token(subject=user.id, role=user.role.value)
        return Token(access_token=token, role=user.role.value, user_id=user.id, username=user.username,
                     phonenumber=user.phonenumber)

    def signup_by_phone(self, signup_in: UserSignupByPhone, role: Optional[str] = None,
                        device_uuid: Optional[str] = None) -> Dict[str, Any]:
        """
        Slide 24 & 41: tên đăng nhập là số điện thoại; mật khẩu không phải số điện thoại,
        không chứa ký tự đặc biệt; được chọn đăng ký là GV hay HV. Trả về mã xác thực.
        """
        phone = (signup_in.phonenumber or "").strip()
        pwd = (signup_in.password or "").strip()
        if not is_valid_phone(phone):
            raise ApiError(ErrorCodes.PARAMETER_VALUE_INVALID, PHONE_INVALID_MSG)
        err = password_error(pwd, phone)
        if err:
            raise ApiError(ErrorCodes.PARAMETER_VALUE_INVALID, err)
        user_role = parse_role(role)
        existing = self.repo.get_by_phone(phone)
        if existing and existing.is_active:
            raise ApiError(ErrorCodes.USER_EXISTED, "Số điện thoại này đã được đăng ký tài khoản.")
        if existing:
            # Đăng ký lại khi chưa xác thực: cập nhật mật khẩu / vai trò
            existing.hashed_password = get_password_hash(pwd)
            existing.role = user_role
            user = existing
            self.db.commit()
        else:
            user = self.repo.create(username=f"user_{phone}", phonenumber=phone, password=pwd, role=user_role)
            user.is_active = False  # chỉ kích hoạt sau check_verify_code
            user.device_uuid = device_uuid
            self.db.commit()
        code = self._issue_code(phone)
        return {
            "code": ErrorCodes.OK,
            "message": "Đăng ký bước 1 thành công. Vui lòng xác thực mã gửi về điện thoại.",
            "data": {"user_id": user.id, "id": user.id, "phonenumber": phone, "verify_code": code, "role": user_role.value},
        }

    def get_verify_code(self, phone: str) -> Dict[str, Any]:
        phone = (phone or "").strip()
        if not is_valid_phone(phone):
            raise ApiError(ErrorCodes.PARAMETER_VALUE_INVALID, PHONE_INVALID_MSG)
        user = self.repo.get_by_phone(phone)
        if not user:
            raise ApiError(ErrorCodes.USER_NOT_VALIDATED, "Số điện thoại chưa đăng ký tài khoản.", 404)
        if user.is_active:
            raise ApiError(ErrorCodes.USER_EXISTED, "Tài khoản đã được xác thực trước đó.")
        last = self.db.query(VerifyCode).filter(VerifyCode.phonenumber == phone).first()
        if last and last.created_at:
            created = last.created_at if last.created_at.tzinfo else last.created_at.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) - created < timedelta(seconds=VERIFY_CODE_COOLDOWN_SECONDS):
                raise ApiError(ErrorCodes.ACTION_DONE_PREVIOUSLY, f"Vui lòng đợi {VERIFY_CODE_COOLDOWN_SECONDS} giây trước khi lấy mã mới.")
        code = self._issue_code(phone)
        return {"code": ErrorCodes.OK, "message": "OK", "data": {"verify_code": code}}

    def check_verify_code(self, verify_in: VerifyCodeRequest) -> Dict[str, Any]:
        """Slide 8 tuần 2: xác thực mã -> trả token, id; mã cũ bị xóa khỏi server."""
        phone = (verify_in.phonenumber or "").strip()
        code = (verify_in.verify_code or "").strip()
        if not is_valid_phone(phone):
            raise ApiError(ErrorCodes.PARAMETER_VALUE_INVALID, PHONE_INVALID_MSG)
        if not code:
            raise ApiError(ErrorCodes.PARAMETER_NOT_ENOUGH, "Thiếu mã xác thực.")
        user = self.repo.get_by_phone(phone)
        if not user:
            raise ApiError(ErrorCodes.USER_NOT_VALIDATED, "Số điện thoại chưa đăng ký tài khoản.", 404)
        if user.is_active and user.session_id:
            raise ApiError(ErrorCodes.USER_EXISTED, "Tài khoản đã được xác thực trước đó.")
        record = self.db.query(VerifyCode).filter(VerifyCode.phonenumber == phone).first()
        if not record or record.code != code:
            raise ApiError(ErrorCodes.PARAMETER_VALUE_INVALID, "Mã xác thực không chính xác.")
        self.db.delete(record)
        user.is_active = True
        self.db.commit()
        token = self._new_session_token(user)
        return {
            "code": ErrorCodes.OK, "message": "Xác nhận mã thành công.",
            "data": {"token": token, "id": user.id, "phonenumber": user.phonenumber, "active": 1, "role": user.role.value},
        }

    def change_info_after_signup(self, user_id: int, info_in: ChangeInfoAfterSignupRequest) -> Dict[str, Any]:
        """Slide 14 tuần 2: đổi username hiển thị, chiều cao (cm) và avatar."""
        user = self.repo.get_by_id(user_id)
        if not user:
            raise ApiError(ErrorCodes.USER_NOT_VALIDATED, "Người dùng không tồn tại.", 404)
        if info_in.username is not None:
            err = username_error(info_in.username, user.phonenumber)
            if err:
                raise ApiError(ErrorCodes.PARAMETER_VALUE_INVALID, err)
            other = self.repo.get_by_username(info_in.username.strip())
            if other and other.id != user.id:
                raise ApiError(ErrorCodes.USER_EXISTED, "Tên người dùng đã được sử dụng.")
        if info_in.height is not None and (info_in.height < 50 or info_in.height > 250):
            raise ApiError(ErrorCodes.PARAMETER_VALUE_INVALID, "Chiều cao không hợp lệ (phải từ 50cm đến 250cm).")
        updated = self.repo.update_profile(
            user_id=user_id, username=info_in.username.strip() if info_in.username else None,
            height=info_in.height, avatar_url=info_in.avatar_url,
        )
        return {
            "code": ErrorCodes.OK, "message": "Cập nhật thông tin thành công.",
            "data": {
                "id": updated.id, "username": updated.username, "phonenumber": updated.phonenumber,
                "email": updated.email, "height": updated.height, "avatar": updated.avatar_url,
                "created": iso(updated.created_at), "status": "active" if updated.is_active else "inactive",
                "url": f"/profile/{updated.id}",
            },
        }

    def login(self, login_data: UserLogin, device_uuid: Optional[str] = None) -> Token:
        user = self.repo.get_by_username_or_email(login_data.username_or_email)
        if not user or not verify_password(login_data.password, user.hashed_password):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Tên đăng nhập hoặc mật khẩu không chính xác.")
        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tài khoản chưa được xác thực hoặc đã bị khóa.")
        token = self._new_session_token(user, device_uuid)
        return Token(access_token=token, role=user.role.value, user_id=user.id, username=user.username,
                     phonenumber=user.phonenumber)

    # ------------------------------------------------------------------------------------------
    # API theo đặc tả
    # ------------------------------------------------------------------------------------------
    def login_by_phone(self, phone: str, password: str, device_uuid: Optional[str] = None) -> Dict[str, Any]:
        phone = (phone or "").strip()
        if not is_valid_phone(phone):
            raise ApiError(ErrorCodes.PARAMETER_VALUE_INVALID, PHONE_INVALID_MSG)
        if password_error(password):
            raise ApiError(ErrorCodes.PARAMETER_VALUE_INVALID, "Sai số điện thoại hoặc mật khẩu.")
        user = self.repo.get_by_phone(phone)
        if not user or not verify_password(password, user.hashed_password):
            raise ApiError(ErrorCodes.USER_NOT_VALIDATED, "Sai số điện thoại hoặc mật khẩu.", 401)
        if not user.is_active:
            raise ApiError(ErrorCodes.USER_NOT_VALIDATED, "Tài khoản chưa được xác thực hoặc đã bị khóa.", 403)
        token = self._new_session_token(user, device_uuid)
        needs_info = user.username.startswith("user_") or not user.height
        return {
            "id": user.id, "username": user.username, "token": token,
            "avatar": "-1" if needs_info else (user.avatar_url or ""),
            "role": user.role.value, "role_label": role_label(user), "phonenumber": user.phonenumber,
            "full_name": user.full_name,
        }

    def logout(self, user: User) -> None:
        # Đổi sang phiên mới không cấp cho token nào -> mọi token cũ hết hiệu lực
        user.session_id = uuid.uuid4().hex
        user.devtoken = None
        self.db.commit()

    def change_password(self, user: User, password: str, new_password: str) -> None:
        if not verify_password(password or "", user.hashed_password):
            raise ApiError(ErrorCodes.PARAMETER_VALUE_INVALID, "Mật khẩu hiện tại không đúng.")
        err = password_error(new_password, user.phonenumber)
        if err:
            raise ApiError(ErrorCodes.PARAMETER_VALUE_INVALID, err)
        if new_password == password:
            raise ApiError(ErrorCodes.PARAMETER_VALUE_INVALID, "Mật khẩu mới phải khác mật khẩu cũ.")
        user.hashed_password = get_password_hash(new_password)
        self.db.commit()

    def set_devtoken(self, user: User, devtype: Optional[str], devtoken: str) -> None:
        user.devtype = (devtype or "")[:10]
        user.devtoken = devtoken[:255]
        self.db.commit()
