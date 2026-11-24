import os
from fastapi import Depends, HTTPException, status, UploadFile, File
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from ..core.database import get_db
from ..core.config import settings
from ..core.security import decode_access_token
from ..repositories.user_repository import UserRepository
from ..models.entities import User, UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Không thể xác thực thông tin đăng nhập.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception
    user_id = payload.get("sub")
    if user_id is None:
        raise credentials_exception
    
    repo = UserRepository(db)
    user = repo.get_by_id(int(user_id))
    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Tài khoản không hoạt động.")
    if not session_matches(user, payload):
        raise credentials_exception
    return user

def session_matches(user: User, payload: dict) -> bool:
    """
    Token chỉ hợp lệ với phiên đăng nhập mới nhất: đăng nhập ở máy khác sẽ làm token cũ
    hết hiệu lực (Slide 28, 34). Token cấp trước khi có cơ chế phiên (không có sid) chỉ
    được chấp nhận khi người dùng chưa từng đăng nhập theo cơ chế mới.
    """
    sid = payload.get("sid")
    if user.session_id is None:
        return True
    return sid == user.session_id

optional_oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login", auto_error=False)

def get_optional_user(token: str = Depends(optional_oauth2_scheme), db: Session = Depends(get_db)):
    """Người dùng hiện tại nếu có token hợp lệ, ngược lại None (API cho phép khách xem)."""
    if not token:
        return None
    try:
        return get_current_user(token, db)
    except HTTPException:
        return None

def get_current_coach(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.COACH and current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ Huấn luyện viên (Coach) mới có quyền thực hiện thao tác này."
        )
    return current_user

async def validate_video_file(file: UploadFile = File(...)) -> UploadFile:
    """
    Xác thực file upload:
    1. Kiểm tra phần mở rộng file (Extension)
    2. Kiểm tra Content-Type
    3. Kiểm tra dung lượng tối đa (MAX_UPLOAD_SIZE_MB)
    """
    filename = file.filename or ""
    ext = os.path.splitext(filename)[1].lower()
    
    if ext not in settings.allowed_extension_list:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Định dạng file không hợp lệ ({ext}). Chỉ chấp nhận: {settings.ALLOWED_EXTENSIONS}"
        )

    content_type = file.content_type or ""
    if not content_type.startswith("video/") and content_type != "application/octet-stream":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File tải lên phải là video hợp lệ (nhận diện: {content_type})."
        )

    # Đọc chunk đầu tiên để kiểm tra dung lượng
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    content = await file.read()
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Dung lượng file vượt quá giới hạn cho phép ({settings.MAX_UPLOAD_SIZE_MB}MB)."
        )

    # Reset con trỏ file sau khi đọc
    await file.seek(0)
    return file
