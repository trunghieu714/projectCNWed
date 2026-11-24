from celery import Celery
from ..core.config import settings

celery_app = Celery(
    "skill_assessment_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.workers.video_tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,            # Giới hạn tối đa 10 phút / task
    worker_prefetch_multiplier=1,    # GPU chỉ bốc 1 task tại 1 thời điểm
    broker_connection_retry_on_startup=False,
    broker_transport_options={
        "socket_timeout": 1.5,
        "socket_connect_timeout": 1.5
    }
)
