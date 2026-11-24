"""Chat 1-1 (Slide 26-27): không chat nhóm; chặn nhau thì không nhắn tin được nữa."""
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.errors import ApiError, no_access, param_invalid, param_missing
from ..core.text_rules import exceeds_word_limit, sanitize_comment
from ..models.entities import Conversation, Message, User
from .notification_service import NotificationService
from .relationship_service import RelationshipService
from .serializers import iso, user_brief

class ChatService:
    def __init__(self, db: Session):
        self.db = db
        self.rel = RelationshipService(db)

    @staticmethod
    def _pair(a: int, b: int) -> Tuple[int, int]:
        return (a, b) if a < b else (b, a)

    def _partner_id(self, conv: Conversation, user_id: int) -> int:
        return conv.user_b_id if conv.user_a_id == user_id else conv.user_a_id

    def _deleted_for(self, conv: Conversation, user_id: int) -> bool:
        return conv.deleted_by_a if conv.user_a_id == user_id else conv.deleted_by_b

    def _set_deleted(self, conv: Conversation, user_id: int, value: bool) -> None:
        if conv.user_a_id == user_id:
            conv.deleted_by_a = value
        else:
            conv.deleted_by_b = value

    def find(self, user: User, partner_id: Optional[int] = None, conversation_id: Optional[int] = None) -> Conversation:
        if conversation_id:
            conv = self.db.get(Conversation, conversation_id)
        elif partner_id:
            a, b = self._pair(user.id, partner_id)
            conv = self.db.query(Conversation).filter(Conversation.user_a_id == a, Conversation.user_b_id == b).first()
        else:
            raise param_missing("partner_id hoặc conversation_id")
        if not conv or user.id not in (conv.user_a_id, conv.user_b_id):
            raise ApiError("9994", "Không tìm thấy cuộc hội thoại.", 404)
        return conv

    def send(self, user: User, partner_id: int, content: str) -> Dict[str, Any]:
        if partner_id == user.id:
            raise param_invalid("Không thể nhắn tin cho chính mình.")
        partner = self.db.get(User, partner_id)
        if not partner:
            raise ApiError("9995", "Người nhận không tồn tại.", 404)
        if self.rel.is_blocked_between(user.id, partner_id):
            raise no_access("Không thể nhắn tin với người đã chặn / bị chặn.")
        text = sanitize_comment(content or "")
        if not text:
            raise param_missing("content")
        if exceeds_word_limit(text, settings.MAX_WORDS):
            raise param_invalid(f"Tin nhắn vượt quá {settings.MAX_WORDS} từ.")
        a, b = self._pair(user.id, partner_id)
        conv = self.db.query(Conversation).filter(Conversation.user_a_id == a, Conversation.user_b_id == b).first()
        if not conv:
            conv = Conversation(user_a_id=a, user_b_id=b)
            self.db.add(conv)
            self.db.flush()
        conv.deleted_by_a = conv.deleted_by_b = False
        msg = Message(conversation_id=conv.id, sender_id=user.id, content=text)
        self.db.add(msg)
        self.db.commit()
        self.db.refresh(msg)
        NotificationService(self.db).notify(partner_id, "message", "Tin nhắn mới",
                                            f"{user.full_name or user.username}: {text[:80]}", conv.id, user.id)
        return self.serialize_message(msg)

    def serialize_message(self, m: Message) -> Dict[str, Any]:
        return {"message_id": m.id, "id": m.id, "conversation_id": m.conversation_id, "message": m.content,
                "sender": user_brief(self.db.get(User, m.sender_id)), "sender_id": m.sender_id,
                "created": iso(m.created_at), "unread": not m.is_read}

    def list_conversations(self, user: User, index: int, count: int) -> Dict[str, Any]:
        convs = (self.db.query(Conversation)
                 .filter(or_(Conversation.user_a_id == user.id, Conversation.user_b_id == user.id))
                 .order_by(Conversation.updated_at.desc()).all())
        items, unread_total = [], 0
        for c in convs:
            if self._deleted_for(c, user.id):
                continue
            last = self.db.query(Message).filter(Message.conversation_id == c.id).order_by(Message.id.desc()).first()
            if not last:
                continue
            unread = self.db.query(Message).filter(Message.conversation_id == c.id, Message.sender_id != user.id,
                                                   Message.is_read.is_(False)).count()
            unread_total += 1 if unread else 0
            items.append({
                "id": c.id, "partner": user_brief(self.db.get(User, self._partner_id(c, user.id))),
                "lastmessage": {"message": last.content, "created": iso(last.created_at), "unread": unread > 0,
                                "sender_id": last.sender_id},
                "unread_count": unread,
            })
        return {"conversations": items[index:index + count], "numNewMessage": unread_total}

    def messages(self, user: User, partner_id: Optional[int], conversation_id: Optional[int],
                 index: int, count: int) -> Dict[str, Any]:
        conv = self.find(user, partner_id, conversation_id)
        partner_id = self._partner_id(conv, user.id)
        q = self.db.query(Message).filter(Message.conversation_id == conv.id).order_by(Message.id.desc())
        rows = list(reversed(q.offset(index).limit(count).all()))
        return {"conversation_id": conv.id, "partner": user_brief(self.db.get(User, partner_id)),
                "is_blocked": self.rel.is_blocked_between(user.id, partner_id),
                "conversation": [self.serialize_message(m) for m in rows]}

    def set_read(self, user: User, partner_id: Optional[int], conversation_id: Optional[int]) -> None:
        conv = self.find(user, partner_id, conversation_id)
        self.db.query(Message).filter(Message.conversation_id == conv.id, Message.sender_id != user.id).update(
            {Message.is_read: True}, synchronize_session=False)
        self.db.commit()

    def delete_message(self, user: User, message_id: int) -> None:
        msg = self.db.get(Message, message_id)
        if not msg:
            raise ApiError("9994", "Tin nhắn không tồn tại.", 404)
        if msg.sender_id != user.id:
            raise no_access("Chỉ được xóa tin nhắn do mình gửi.")
        self.db.delete(msg)
        self.db.commit()

    def delete_conversation(self, user: User, partner_id: Optional[int], conversation_id: Optional[int]) -> None:
        conv = self.find(user, partner_id, conversation_id)
        self._set_deleted(conv, user.id, True)
        if conv.deleted_by_a and conv.deleted_by_b:
            self.db.delete(conv)
        self.db.commit()
