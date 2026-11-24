"""
Các quy tắc kiểm tra dữ liệu dùng chung cho cả server (client cũng kiểm tra lại cùng quy tắc).
Thông báo lỗi được giữ thống nhất giữa các màn hình (Slide 34).
"""
import re
import unicodedata
from typing import List, Optional

PHONE_INVALID_MSG = "Số điện thoại không đúng định dạng."
PASSWORD_INVALID_MSG = "Mật khẩu phải từ 6 đến 30 ký tự, không chứa ký tự đặc biệt và không trùng số điện thoại."

_PHONE_RE = re.compile(r"^0\d{9}$")
_PASSWORD_RE = re.compile(r"^[A-Za-z0-9]{6,30}$")
_USERNAME_FORBIDDEN_RE = re.compile(r"[<>{}\[\]\\/@#$%^&*=+|~`\"';:!?]")
_URL_RE = re.compile(r"(https?://|www\.)", re.IGNORECASE)
_HTML_TAG_RE = re.compile(r"<[^>]+>")

def is_valid_phone(phone: Optional[str]) -> bool:
    return bool(phone) and bool(_PHONE_RE.match(phone.strip()))

def password_error(password: Optional[str], phone: Optional[str] = None) -> Optional[str]:
    """Slide 24: mật khẩu không phải là số điện thoại, không chứa ký tự đặc biệt."""
    if not password or not _PASSWORD_RE.match(password):
        return PASSWORD_INVALID_MSG
    if phone and password == phone.strip():
        return PASSWORD_INVALID_MSG
    return None

def username_error(username: Optional[str], phone: Optional[str] = None) -> Optional[str]:
    """
    Slide 16 tuần 2: username không chứa ký tự đặc biệt, không trùng số điện thoại,
    không để trống, không quá ngắn/quá dài, không phải đường dẫn hay số điện thoại.
    """
    if username is None or not username.strip():
        return "Tên người dùng không được để trống."
    name = username.strip()
    if len(name) < 2 or len(name) > 50:
        return "Tên người dùng phải từ 2 đến 50 ký tự."
    if _USERNAME_FORBIDDEN_RE.search(name):
        return "Tên người dùng không được chứa ký tự đặc biệt."
    if _URL_RE.search(name) or re.search(r"\.(com|vn|net|org)\b", name, re.IGNORECASE):
        return "Tên người dùng không được là đường dẫn."
    digits = re.sub(r"\D", "", name)
    if (phone and digits == phone.strip()) or re.fullmatch(r"[\d\s+.-]{8,}", name):
        return "Tên người dùng không được là số điện thoại."
    return None

def count_words(text: Optional[str]) -> int:
    return len((text or "").split())

def exceeds_word_limit(text: Optional[str], limit: int) -> bool:
    return count_words(text) > limit

def sanitize_comment(text: str) -> str:
    """Bình luận chỉ chứa văn bản, HTTP link và/hoặc emoticon (Slide 28): loại bỏ thẻ HTML."""
    return _HTML_TAG_RE.sub("", text or "").strip()

def strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text or "")
    no_marks = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    return no_marks.replace("đ", "d").replace("Đ", "D")

def search_tokens(text: str) -> List[str]:
    """Tách từ khóa tìm kiếm: không phân biệt hoa thường, dấu và thứ tự từ (Slide 31)."""
    cleaned = re.sub(r"[^\w\s#]", " ", strip_accents(text).lower())
    return [t for t in cleaned.split() if t]

def matches_all_tokens(haystack: str, tokens: List[str]) -> bool:
    words = set(search_tokens(haystack))
    return all(t in words for t in tokens)
