import os
from typing import List, Optional, Union
from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "Skill Assessment Platform API"
    API_V1_STR: str = "/api/v1"
    # Prefix của bộ API theo đúng đặc tả restful_api (POST api/<tên_api>)
    API_SPEC_STR: str = "/api"
    # Prefix tương thích server kỳ 20252 (Mercari-server: POST it4788/<tên_api>); để trống để tắt
    API_COMPAT_STR: str = "/it4788"
    APP_VERSION: str = "1.2.0"

    # Database
    DATABASE_URL: str = "sqlite:///./app.db"

    # Security & Auth (.env.example dùng SECRET_KEY nên chấp nhận cả hai tên biến)
    JWT_SECRET_KEY: str = Field(
        default="super-secret-key-change-this-in-production-use-openssl-rand-hex-32",
        validation_alias=AliasChoices("JWT_SECRET_KEY", "SECRET_KEY"),
    )
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

    # CORS: Allow specific origins (comma separated string converted to list)
    CORS_ORIGINS: Union[str, List[str]] = "http://localhost:3000,http://127.0.0.1:3000,http://103.75.182.246"

    @field_validator("CORS_ORIGINS", mode="before")
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    # Redis / Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"

    # Media Storage & Upload Validation
    MAX_UPLOAD_SIZE_MB: int = 150
    ALLOWED_EXTENSIONS: str = ".mp4,.avi,.mov,.mkv,.webm"
    UPLOAD_DIR: str = "storage/uploads"
    OUTPUT_DIR: str = "storage/outputs"
    COACH_SAMPLES_DIR: str = "storage/coach_samples"
    POSE_CACHE_DIR: str = "storage/pose_cache"
    AVATAR_DIR: str = "storage/avatars"
    # Slide 25 & 29: video tối thiểu 10 giây
    MIN_VIDEO_SECONDS: float = 10.0
    # Slide 24 & 25: bài viết và bình luận tối đa 500 từ
    MAX_WORDS: int = 500
    MAX_AVATAR_SIZE_MB: int = 5
    FFMPEG_BINARY: str = "ffmpeg"

    # AI Pipeline
    # mock | precomputed | yolo | remote | tcpformer  (có thể ghép fallback: "precomputed,yolo,mock")
    AI_ESTIMATOR_TYPE: str = "precomputed,mock"
    # pa_mpjpe_dtw (chuẩn code mẫu của GV) | dtw (góc khớp)
    AI_SCORER_TYPE: str = "pa_mpjpe_dtw"
    AI_VISUALIZER_TYPE: str = "fused_video"
    # URL server AI (Colab / máy có GPU chạy WHAM/GVHMR) - FAQ Q5
    AI_REMOTE_URL: Optional[str] = None
    AI_REMOTE_TIMEOUT: int = 900
    # Khóa gửi kèm header X-API-Key tới pose server (trùng POSE_SERVER_KEY in ra ở notebook Colab)
    AI_REMOTE_API_KEY: Optional[str] = None
    # Chu kỳ hỏi trạng thái job (giây); GVHMR chạy vài phút, vượt giới hạn 100s/request của Cloudflare tunnel
    AI_REMOTE_POLL_INTERVAL: float = 5.0
    # Trọng số YOLO pose (YOLO26x theo đề, có thể thay bằng yolo11n-pose.pt khi máy yếu)
    YOLO_POSE_WEIGHTS: str = "yolo26x-pose.pt"
    # File hiệu chỉnh 2 camera (ma trận chiếu P1, P2) để fusion 2 bộ pose2D thành 3D (Slide 10)
    AI_CAMERA_CALIB_PATH: Optional[str] = None
    # Thông số chấm điểm DTW
    DTW_WINDOW_RATIO: float = 0.1
    SCORE_ERROR_TOLERANCE: float = 0.12
    SCORE_MAX_ERROR: float = 0.45

    # Firebase (push notification + báo cho local host có bài mới - Slide 8, FAQ Q3 & Q10)
    FIREBASE_CREDENTIALS: Optional[str] = None
    FIREBASE_DB_URL: Optional[str] = None

    # Phiên bản ứng dụng cho check_new_version
    CLIENT_LATEST_VERSION: str = "1.2.0"
    CLIENT_REQUIRED_VERSION: str = "1.0.0"

    @property
    def allowed_extension_list(self) -> List[str]:
        return [ext.strip().lower() for ext in self.ALLOWED_EXTENSIONS.split(",")]

    @property
    def estimator_chain(self) -> List[str]:
        return [x.strip().lower() for x in self.AI_ESTIMATOR_TYPE.split(",") if x.strip()]

    model_config = SettingsConfigDict(env_file=(".env", "backend/.env", "../.env"), extra="allow", case_sensitive=True, populate_by_name=True)

settings = Settings()
