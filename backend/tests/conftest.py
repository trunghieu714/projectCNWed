"""
Cấu hình kiểm thử: dùng DB SQLite và thư mục storage tạm riêng, không đụng vào app.db / storage thật.
Phải chạy trước khi import app (pytest nạp conftest trước các file test).
"""
import os
import sys
import tempfile
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

_TMP = Path(tempfile.mkdtemp(prefix="skill_test_"))
# TEST_DATABASE_URL=postgresql://... để chạy toàn bộ test trên PostgreSQL (giống môi trường Docker)
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{(_TMP / 'test.db').as_posix()}"
os.environ["AI_ESTIMATOR_TYPE"] = "precomputed,mock"
os.environ["AI_SCORER_TYPE"] = "pa_mpjpe_dtw"
os.environ["FIREBASE_CREDENTIALS"] = ""
os.environ["CELERY_BROKER_URL"] = "redis://127.0.0.1:1/0"  # không có Redis -> chấm đồng bộ
os.chdir(_TMP)

from app.core.database import init_db  # noqa: E402

init_db()
