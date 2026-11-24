"""
Bộ API theo đúng đặc tả 'Mô tả restful_api - Website Tập động tác diễu binh diễu hành.xlsx':
mọi API dạng POST {base}/api/<tên_api>, response {code, message, data} với mã lỗi chuẩn.
"""
from fastapi import APIRouter

from . import admin, auth, posts, social, users

spec_router = APIRouter()
for module in (auth, posts, users, social, admin):
    spec_router.include_router(module.router)
