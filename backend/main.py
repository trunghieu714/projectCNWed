from contextlib import asynccontextmanager
import os
import re
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.core.config import settings
from app.core.database import init_db
from app.core.errors import ApiError, api_error_handler
from app.api.v1.api import api_router
from app.api.spec.router import spec_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Khởi tạo bảng cơ sở dữ liệu và thư mục lưu trữ khi khởi động
    init_db()
    os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(settings.COACH_SAMPLES_DIR, exist_ok=True)
    os.makedirs(settings.POSE_CACHE_DIR, exist_ok=True)
    os.makedirs(settings.AVATAR_DIR, exist_ok=True)
    yield
    # Dọn dẹp tài nguyên khi tắt server nếu cần

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.APP_VERSION,
    description="Skill Assessment & Motion Coaching API (Clean Architecture & Async Celery Worker)",
    lifespan=lifespan
)
app.add_exception_handler(ApiError, api_error_handler)

# Cấu hình CORS an toàn theo danh sách domain cấu hình
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Streaming video với hỗ trợ HTTP 206 Partial Content (Range header) chuẩn cho mọi trình duyệt
@app.get("/storage/{file_path:path}")
async def stream_storage_file(file_path: str, request: Request):
    full_path = os.path.join("storage", file_path)
    if not os.path.isfile(full_path):
        raise HTTPException(status_code=404, detail="Không tìm thấy tệp.")

    real_root = os.path.realpath("storage")
    if not os.path.realpath(full_path).startswith(real_root + os.sep):
        raise HTTPException(status_code=404, detail="Không tìm thấy tệp.")
    import mimetypes
    content_type = mimetypes.guess_type(full_path)[0] or "application/octet-stream"
    if full_path.endswith((".mp4", ".mov", ".m4v")):
        content_type = "video/mp4"
    file_size = os.path.getsize(full_path)
    range_header = request.headers.get("range")

    if not range_header:
        return FileResponse(full_path, media_type=content_type, headers={"Accept-Ranges": "bytes"})

    range_match = re.match(r"bytes=(\d+)-(\d*)", range_header)
    if not range_match:
        return FileResponse(full_path, media_type=content_type, headers={"Accept-Ranges": "bytes"})

    start = int(range_match.group(1))
    end = int(range_match.group(2)) if range_match.group(2) else file_size - 1
    if start >= file_size or end >= file_size or start > end:
        return StreamingResponse(
            status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
            headers={"Content-Range": f"bytes */{file_size}"}
        )

    chunk_size = 1024 * 1024  # 1MB
    content_length = end - start + 1

    def file_iterator():
        with open(full_path, "rb") as f:
            f.seek(start)
            bytes_left = content_length
            while bytes_left > 0:
                read_bytes = min(chunk_size, bytes_left)
                data = f.read(read_bytes)
                if not data:
                    break
                bytes_left -= len(data)
                yield data

    headers = {
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(content_length),
        "Content-Type": content_type,
    }
    return StreamingResponse(file_iterator(), status_code=status.HTTP_206_PARTIAL_CONTENT, headers=headers)

# Phục vụ thư mục static chứa video output (fallback)
os.makedirs("storage", exist_ok=True)
app.mount("/storage", StaticFiles(directory="storage"), name="storage")

# Đăng ký Router V1 (REST) và bộ API theo đúng đặc tả restful_api (POST /api/<tên_api>)
app.include_router(api_router, prefix=settings.API_V1_STR)
app.include_router(spec_router, prefix=settings.API_SPEC_STR, tags=["API theo đặc tả"])

@app.get("/")
def root():
    return {
        "status": "online",
        "docs_url": "/docs",
        "version": settings.APP_VERSION,
        "description": "Skill Assessment API with FastDTW, TCPFormer, Celery & JWT Auth"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
