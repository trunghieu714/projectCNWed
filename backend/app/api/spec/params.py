"""
Đọc tham số cho bộ API theo đặc tả restful_api: mọi API là POST, tham số có thể gửi bằng
form-data / x-www-form-urlencoded / JSON / query string; token gửi trong tham số `token`
hoặc header `Authorization: Bearer`.
Lỗi thiếu tham số -> 1002, sai kiểu -> 1003, sai giá trị -> 1004, token sai -> 9998.
"""
from typing import Any, Dict, Optional

from fastapi import Depends, Request
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile as StarletteUploadFile

from ...core.database import get_db
from ...core.errors import ApiError
from ...core.security import decode_access_token
from ...models.entities import User, UserRole
from ..deps import session_matches

class Params:
    def __init__(self, data: Dict[str, Any], files: Dict[str, Any], headers):
        self.data = data
        self.files = files
        self.headers = headers

    def raw(self, name: str) -> Any:
        v = self.data.get(name)
        return None if v is None or (isinstance(v, str) and v.strip() == "") else v

    def str(self, name: str, required: bool = False, max_len: Optional[int] = None) -> Optional[str]:
        v = self.raw(name)
        if v is None:
            if required:
                raise ApiError("1002", f"Thiếu tham số {name}.")
            return None
        s = v if isinstance(v, str) else str(v)
        if max_len and len(s) > max_len:
            raise ApiError("1004", f"Tham số {name} quá dài (tối đa {max_len} ký tự).")
        return s

    def int(self, name: str, required: bool = False, default: Optional[int] = None,
            minimum: Optional[int] = None, maximum: Optional[int] = None) -> Optional[int]:
        v = self.raw(name)
        if v is None:
            if required:
                raise ApiError("1002", f"Thiếu tham số {name}.")
            return default
        try:
            n = int(str(v).strip())
        except (TypeError, ValueError):
            raise ApiError("1003", f"Tham số {name} phải là số nguyên.")
        if minimum is not None and n < minimum:
            raise ApiError("1004", f"Tham số {name} phải ≥ {minimum}.")
        if maximum is not None and n > maximum:
            n = maximum
        return n

    def float(self, name: str, required: bool = False) -> Optional[float]:
        v = self.raw(name)
        if v is None:
            if required:
                raise ApiError("1002", f"Thiếu tham số {name}.")
            return None
        try:
            return float(str(v).strip())
        except (TypeError, ValueError):
            raise ApiError("1003", f"Tham số {name} phải là số.")

    def flag(self, name: str, default: bool = False) -> bool:
        v = self.raw(name)
        if v is None:
            return default
        return str(v).strip().lower() in ("1", "true", "yes", "on")

    def file(self, name: str):
        f = self.files.get(name)
        return f if f is not None and getattr(f, "filename", None) else None

    def page(self, default_count: int = 20):
        return self.int("index", default=0, minimum=0), self.int("count", default=default_count, minimum=1, maximum=100)

    @property
    def token(self) -> Optional[str]:
        t = self.str("token")
        if t:
            return t
        auth = self.headers.get("authorization", "")
        return auth[7:].strip() if auth.lower().startswith("bearer ") else None

async def read_params(request: Request) -> Params:
    data: Dict[str, Any] = dict(request.query_params)
    files: Dict[str, Any] = {}
    ctype = request.headers.get("content-type", "")
    if "application/json" in ctype:
        try:
            body = await request.json()
        except Exception:
            raise ApiError("1003", "Body JSON không hợp lệ.")
        if isinstance(body, dict):
            data.update(body)
    elif "multipart/form-data" in ctype or "application/x-www-form-urlencoded" in ctype:
        form = await request.form()
        for key, value in form.multi_items():
            if isinstance(value, StarletteUploadFile):
                if value.filename:
                    files[key] = value
            else:
                data[key] = value
    return Params(data, files, request.headers)

def _user_from_token(token: Optional[str], db: Session) -> User:
    if not token:
        raise ApiError("1002", "Thiếu mã phiên đăng nhập (token).", 401)
    payload = decode_access_token(token)
    if not payload or not payload.get("sub"):
        raise ApiError("9998", "Mã phiên đăng nhập không hợp lệ hoặc đã hết hạn.", 401)
    user = db.get(User, int(payload["sub"]))
    if not user:
        raise ApiError("9998", "Mã phiên đăng nhập không hợp lệ.", 401)
    if not session_matches(user, payload):
        raise ApiError("9998", "Tài khoản đã đăng nhập trên thiết bị khác. Vui lòng đăng nhập lại.", 401)
    if not user.is_active:
        raise ApiError("9995", "Tài khoản chưa được xác thực hoặc đã bị khóa.", 403)
    return user

class Ctx:
    """Gói tham số + phiên DB + người dùng hiện tại cho mỗi API."""

    def __init__(self, params: Params, db: Session):
        self.p = params
        self.db = db
        self._user: Optional[User] = None
        self._resolved = False

    @property
    def user(self) -> User:
        if self._user is None:
            self._user = _user_from_token(self.p.token, self.db)
        return self._user

    @property
    def optional_user(self) -> Optional[User]:
        """API cho phép không đăng nhập (vd get_list_posts): token sai thì coi như khách."""
        if not self._resolved:
            self._resolved = True
            if self.p.token:
                try:
                    self._user = _user_from_token(self.p.token, self.db)
                except ApiError:
                    self._user = None
        return self._user

    def require_role(self, *roles: UserRole) -> User:
        u = self.user
        if u.role not in roles and u.role != UserRole.ADMIN:
            raise ApiError("1009", "Không có quyền thực hiện thao tác này.", 403)
        return u

async def get_ctx(params: Params = Depends(read_params), db: Session = Depends(get_db)) -> Ctx:
    return Ctx(params, db)
