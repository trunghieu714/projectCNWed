"""
Push notification (Slide 4, 28, 31) + báo sự kiện cho Local Host chấm điểm (Slide 8, FAQ Q3 & Q10).

- Mọi thông báo đều được lưu vào bảng notifications (client đọc qua get_notification / check_new_item).
- Nếu cấu hình FIREBASE_CREDENTIALS và người dùng có devtoken: gửi FCM với âm thanh theo push setting.
- Nếu cấu hình FIREBASE_DB_URL: ghi sự kiện "bài nộp mới" lên Firebase Realtime Database để
  phần mềm/web local trên PC lắng nghe và tải video về chấm.
"""
import logging
import threading
from typing import Any, Dict, Iterable, Optional

from sqlalchemy.orm import Session

from ..core.config import settings
from ..models.entities import Notification, PushSetting, User

logger = logging.getLogger(__name__)

_firebase_lock = threading.Lock()
_firebase_app = None
_firebase_failed = False

# Loại thông báo -> cột push setting tương ứng
TYPE_TO_SETTING = {
    "like": "like_comment", "comment": "like_comment", "new_post": "new_post",
    "submission": "new_post", "message": "message", "enrollment_request": "enrollment",
    "enrollment_result": "enrollment", "score": "score", "login_other_device": None,
}
SOUND_FILES = {1: "default", 2: "voice_notification"}

def _firebase():
    global _firebase_app, _firebase_failed
    if _firebase_app or _firebase_failed or not settings.FIREBASE_CREDENTIALS:
        return _firebase_app
    with _firebase_lock:
        if _firebase_app or _firebase_failed:
            return _firebase_app
        try:
            import firebase_admin
            from firebase_admin import credentials
            options = {"databaseURL": settings.FIREBASE_DB_URL} if settings.FIREBASE_DB_URL else None
            _firebase_app = firebase_admin.initialize_app(credentials.Certificate(settings.FIREBASE_CREDENTIALS), options)
        except Exception as e:
            _firebase_failed = True
            logger.warning("Không khởi tạo được Firebase: %s", e)
    return _firebase_app

class NotificationService:
    def __init__(self, db: Session):
        self.db = db

    def get_settings(self, user_id: int) -> PushSetting:
        ps = self.db.get(PushSetting, user_id)
        if not ps:
            ps = PushSetting(user_id=user_id)
            self.db.add(ps)
            self.db.commit()
            self.db.refresh(ps)
        return ps

    def notify(self, user_id: Optional[int], type_: str, title: str, body: Optional[str] = None,
               object_id: Optional[int] = None, actor_id: Optional[int] = None) -> Optional[Notification]:
        if not user_id or user_id == actor_id:
            return None
        n = Notification(user_id=user_id, type=type_, title=title, body=body, object_id=object_id, actor_id=actor_id)
        self.db.add(n)
        self.db.commit()
        self.db.refresh(n)
        try:
            self._push(n)
        except Exception as e:
            logger.warning("Push thất bại: %s", e)
        return n

    def notify_many(self, user_ids: Iterable[int], type_: str, title: str, body: Optional[str] = None,
                    object_id: Optional[int] = None, actor_id: Optional[int] = None) -> None:
        for uid in set(user_ids):
            self.notify(uid, type_, title, body, object_id, actor_id)

    def _push(self, n: Notification) -> None:
        app = _firebase()
        if not app:
            return
        user = self.db.get(User, n.user_id)
        if not user or not user.devtoken:
            return
        ps = self.get_settings(n.user_id)
        key = TYPE_TO_SETTING.get(n.type)
        if not ps.notification_on or (key and not getattr(ps, key, True)):
            return
        from firebase_admin import messaging
        sound = SOUND_FILES.get(ps.sound_mode)
        msg = messaging.Message(
            token=user.devtoken,
            notification=messaging.Notification(title=n.title, body=n.body or ""),
            data={"type": n.type, "object_id": str(n.object_id or ""), "notification_id": str(n.id)},
            android=messaging.AndroidConfig(notification=messaging.AndroidNotification(sound=sound)) if sound else None,
            apns=messaging.APNSConfig(payload=messaging.APNSPayload(aps=messaging.Aps(sound=sound))) if sound else None,
        )
        messaging.send(msg, app=app)

    @staticmethod
    def publish_event(path: str, payload: Dict[str, Any]) -> None:
        """Ghi sự kiện lên Firebase Realtime Database (vd: 'submissions') cho Local Host lắng nghe."""
        app = _firebase()
        if not app or not settings.FIREBASE_DB_URL:
            return
        try:
            from firebase_admin import db as rtdb
            rtdb.reference(path, app=app).push(payload)
        except Exception as e:
            logger.warning("Không ghi được sự kiện Firebase: %s", e)
