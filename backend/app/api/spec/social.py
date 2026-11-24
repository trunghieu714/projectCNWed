"""Nhóm API thông báo & chat: get_notification, set_read_notification, get_push_settings,
set_push_settings, set_conversation, get_conversation, get_list_conversation, set_read_message,
delete_message, delete_conversation."""
from fastapi import APIRouter, Depends

from ...core.errors import ApiError, ok, param_invalid
from ...models.entities import Notification, User
from ...services.chat_service import ChatService
from ...services.notification_service import NotificationService
from ...services.serializers import iso, user_brief
from .params import Ctx, get_ctx

router = APIRouter()
PUSH_FIELDS = ("like_comment", "new_post", "message", "enrollment", "score")

@router.post("/get_notification")
def get_notification(ctx: Ctx = Depends(get_ctx)):
    user = ctx.user
    index, count = ctx.p.page()
    q = ctx.db.query(Notification).filter(Notification.user_id == user.id)
    rows = q.order_by(Notification.id.desc()).offset(index).limit(count).all()
    unread = q.filter(Notification.is_read.is_(False)).count()
    return ok({
        "notifications": [{
            "notification_id": n.id, "id": n.id, "type": n.type, "object_id": n.object_id, "title": n.title,
            "body": n.body, "created": iso(n.created_at), "read": n.is_read,
            "actor": user_brief(ctx.db.get(User, n.actor_id)) if n.actor_id else None,
        } for n in rows],
        "badge": unread,
        "last_update": iso(rows[0].created_at) if rows else None,
    })

@router.post("/set_read_notification")
def set_read_notification(ctx: Ctx = Depends(get_ctx)):
    user = ctx.user
    q = ctx.db.query(Notification).filter(Notification.user_id == user.id)
    if not ctx.p.flag("all"):
        nid = ctx.p.int("notification_id", required=True)
        q = q.filter(Notification.id == nid)
        if not q.first():
            raise ApiError("9994", "Không tìm thấy thông báo.", 404)
    q.update({Notification.is_read: True}, synchronize_session=False)
    ctx.db.commit()
    return ok({"badge": ctx.db.query(Notification).filter(Notification.user_id == user.id, Notification.is_read.is_(False)).count()})

def _push_dict(ps):
    return {"notification_on": ps.notification_on, "sound_mode": ps.sound_mode, **{f: getattr(ps, f) for f in PUSH_FIELDS}}

@router.post("/get_push_settings")
@router.post("/get_push_setting")
def get_push_settings(ctx: Ctx = Depends(get_ctx)):
    return ok(_push_dict(NotificationService(ctx.db).get_settings(ctx.user.id)))

@router.post("/set_push_settings")
@router.post("/set_push_setting")
def set_push_settings(ctx: Ctx = Depends(get_ctx)):
    """sound_mode: 0 tắt âm, 1 âm mặc định, 2 âm giọng nói; các cờ 0/1 cho từng loại thông báo."""
    ps = NotificationService(ctx.db).get_settings(ctx.user.id)
    changed = False
    if ctx.p.raw("notification_on") is not None:
        ps.notification_on = ctx.p.flag("notification_on")
        changed = True
    if ctx.p.raw("sound_mode") is not None:
        mode = ctx.p.int("sound_mode")
        if mode not in (0, 1, 2):
            raise param_invalid("sound_mode chỉ nhận 0, 1, 2.")
        ps.sound_mode = mode
        changed = True
    for f in PUSH_FIELDS:
        if ctx.p.raw(f) is not None:
            setattr(ps, f, ctx.p.flag(f))
            changed = True
    if not changed:
        raise ApiError("1002", "Cần tối thiểu một thiết lập để cập nhật.")
    ctx.db.commit()
    return ok(_push_dict(ps))

# ---------------------------------------------------------------------------------------------- chat
@router.post("/set_conversation")
@router.post("/set_send_message")
def set_conversation(ctx: Ctx = Depends(get_ctx)):
    """Gửi tin nhắn. Input: token, partner_id hoặc conversation_id, content (hoặc message như server 20252)."""
    chat = ChatService(ctx.db)
    partner_id = ctx.p.int("partner_id")
    if partner_id is None:
        conversation_id = ctx.p.int("conversation_id")
        if conversation_id is None:
            raise ApiError("1002", "Thiếu partner_id hoặc conversation_id.")
        partner_id = chat._partner_id(chat.find(ctx.user, conversation_id=conversation_id), ctx.user.id)
    content = ctx.p.str("content") if ctx.p.raw("content") is not None else ctx.p.str("message", required=True)
    return ok(chat.send(ctx.user, partner_id, content))

@router.post("/get_list_conversation")
def get_list_conversation(ctx: Ctx = Depends(get_ctx)):
    index, count = ctx.p.page()
    return ok(ChatService(ctx.db).list_conversations(ctx.user, index, count))

@router.post("/get_conversation")
def get_conversation(ctx: Ctx = Depends(get_ctx)):
    index, count = ctx.p.page(50)
    return ok(ChatService(ctx.db).messages(ctx.user, ctx.p.int("partner_id"), ctx.p.int("conversation_id"), index, count))

@router.post("/set_read_message")
def set_read_message(ctx: Ctx = Depends(get_ctx)):
    ChatService(ctx.db).set_read(ctx.user, ctx.p.int("partner_id"), ctx.p.int("conversation_id"))
    return ok(None)

@router.post("/delete_message")
def delete_message(ctx: Ctx = Depends(get_ctx)):
    ChatService(ctx.db).delete_message(ctx.user, ctx.p.int("message_id", required=True))
    return ok(None)

@router.post("/delete_conversation")
def delete_conversation(ctx: Ctx = Depends(get_ctx)):
    ChatService(ctx.db).delete_conversation(ctx.user, ctx.p.int("partner_id"), ctx.p.int("conversation_id"))
    return ok(None)
