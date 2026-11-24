from typing import List, Optional
from sqlalchemy.orm import Session
from ..models.entities import Comment

class CommentRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, post_id: int, content: str, user_id: Optional[int] = None, is_bot_evaluation: bool = False) -> Comment:
        comment = Comment(
            post_id=post_id,
            user_id=user_id,
            content=content,
            is_bot_evaluation=is_bot_evaluation
        )
        self.db.add(comment)
        self.db.commit()
        self.db.refresh(comment)
        return comment

    def get_by_post(self, post_id: int, skip: int = 0, limit: int = 50) -> List[Comment]:
        return (
            self.db.query(Comment)
            .filter(Comment.post_id == post_id)
            .order_by(Comment.created_at.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )
