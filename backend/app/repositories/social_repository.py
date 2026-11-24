from typing import List, Optional
from sqlalchemy.orm import Session
from ..models.entities import SocialPost, User, Submission, Comment

class SocialRepository:
    """
    Repository cho Mạng xã hội luyện tập (Social Posts).
    Tuân thủ Slide 6 & 7:
    - Hỗ trợ tối đa 2 video góc quay
    - Tự động liên kết khóa học (course_id) và bài tập (exercise_id)
    - Tự động tải kèm danh sách bình luận (bao gồm bình luận chấm điểm của AI Bot)
    """

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, post_id: int) -> Optional[SocialPost]:
        return self.db.query(SocialPost).filter(SocialPost.id == post_id).first()

    def get_feed(self, skip: int = 0, limit: int = 30) -> List[dict]:
        posts = (
            self.db.query(SocialPost)
            .order_by(SocialPost.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        
        feed = []
        for p in posts:
            author = self.db.query(User).filter(User.id == p.user_id).first()
            sub = self.db.query(Submission).filter(Submission.id == p.submission_id).first() if p.submission_id else None
            comments = self.db.query(Comment).filter(Comment.post_id == p.id).order_by(Comment.created_at.asc()).all()
            
            feed.append({
                "id": p.id,
                "user_id": p.user_id,
                "course_id": p.course_id,
                "exercise_id": p.exercise_id,
                "submission_id": p.submission_id,
                "content": p.content,
                "video_left_url": p.video_left_url,
                "video_right_url": p.video_right_url,
                "video_fused_url": p.video_fused_url,
                "device_master": p.device_master,
                "device_slave": p.device_slave,
                "likes_count": p.likes_count,
                "created_at": p.created_at,
                "updated_at": p.updated_at,
                "author": author,
                "submission": sub,
                "comments": comments
            })
        return feed

    def create(
        self,
        user_id: int,
        content: str,
        submission_id: Optional[int] = None,
        course_id: Optional[int] = None,
        exercise_id: Optional[int] = None,
        video_left_url: Optional[str] = None,
        video_right_url: Optional[str] = None,
        video_fused_url: Optional[str] = None,
        device_master: Optional[str] = None,
        device_slave: Optional[str] = None
    ) -> SocialPost:
        post = SocialPost(
            user_id=user_id,
            content=content,
            submission_id=submission_id,
            course_id=course_id,
            exercise_id=exercise_id,
            video_left_url=video_left_url,
            video_right_url=video_right_url,
            video_fused_url=video_fused_url,
            device_master=device_master,
            device_slave=device_slave,
            likes_count=0
        )
        self.db.add(post)
        self.db.commit()
        self.db.refresh(post)
        return post

    def edit(
        self,
        post_id: int,
        content: Optional[str] = None,
        video_left_url: Optional[str] = None,
        video_right_url: Optional[str] = None
    ) -> Optional[SocialPost]:
        post = self.get_by_id(post_id)
        if not post:
            return None

        if content is not None:
            post.content = content
        if video_left_url is not None:
            post.video_left_url = video_left_url
        if video_right_url is not None:
            post.video_right_url = video_right_url

        self.db.commit()
        self.db.refresh(post)
        return post

    def like_post(self, post_id: int) -> Optional[SocialPost]:
        post = self.get_by_id(post_id)
        if post:
            post.likes_count += 1
            self.db.commit()
            self.db.refresh(post)
        return post
