from typing import Any, Optional
from fastapi import Request
from fastapi.responses import JSONResponse

class ApiError(Exception):
    """
    Lỗi nghiệp vụ trả về đúng định dạng response(common) của đặc tả:
    {"code": "<mã>", "message": "<thông báo>", "data": null}
    """

    def __init__(self, code: str, message: str, http_status: int = 400, data: Any = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
        self.data = data

async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.http_status,
        content={"code": exc.code, "message": exc.message, "data": exc.data},
    )

def ok(data: Any = None, message: str = "OK") -> dict:
    return {"code": "1000", "message": message, "data": data}

def not_found_post() -> ApiError:
    return ApiError("9992", "Bài viết không tồn tại.", 404)

def no_access(message: str = "Không có quyền truy cập tài nguyên.") -> ApiError:
    return ApiError("1009", message, 403)

def param_missing(name: Optional[str] = None) -> ApiError:
    return ApiError("1002", f"Thiếu tham số {name}." if name else "Số lượng tham số không đầy đủ.", 400)

def param_invalid(message: str = "Giá trị tham số không hợp lệ.") -> ApiError:
    return ApiError("1004", message, 400)
