"""
Nghiệp vụ mạng xã hội luyện tập theo đặc tả đề tài (Slide 5-8, 24-31; bài tập tuần 2-3).

Quy ước định danh theo đặc tả add_post (Slide 40 tuần 2):
- Bài đăng có video của GV chính là một bài tập: exercise_id = id bài viết của GV.
- course_id = id của giáo viên (mỗi GV chỉ có 1 khóa học).
"""
import json
import logging
import os
import threading
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.errors import ApiError, no_access, not_found_post, param_invalid, param_missing
from ..core.text_rules import exceeds_word_limit, matches_all_tokens, sanitize_comment, search_tokens
from ..models.entities import (Comment, Course, Exercise, PostLike, PostReport, SavedSearch, SocialPost,
                               Submission, User, UserRole)
from .notification_service import NotificationService
from .relationship_service import CourseService, RelationshipService
from .serializers import iso, submission_brief, user_brief
from . import video_service

logger = logging.getLogger(__name__)
VALID_SIDES = {"L", "R"}

def run_in_background(background, fn: Callable, *args) -> None:
    """Chạy tác vụ nặng sau khi trả response (FastAPI BackgroundTasks) hoặc trong thread riêng."""
    if background is not None:
        background.add_task(fn, *args)
    else:
        threading.Thread(target=fn, args=args, daemon=True).start()

def parse_video_indices(raw: Optional[str]) -> Set[str]:
    """edit_post: 'L' | 'R' | 'LR' | 'all' (có thể có dấu phẩy / khoảng trắng)."""
    if raw is None or str(raw).strip() == "":
        return set()
    value = str(raw).strip().upper().replace(",", "").replace(" ", "")
    if value in ("ALL", "LR", "RL"):
        return {"L", "R"}
    if value in VALID_SIDES:
        return {value}
    raise param_invalid("video_indices chỉ nhận L, R, LR hoặc all.")

class PostService:
    def __init__(self, db: Session, background=None):
        self.db = db
        self.background = background
        self.rel = RelationshipService(db)
        self.courses = CourseService(db)
        self.notifier = NotificationService(db)

    # ------------------------------------------------------------------------------------------
    # Tra cứu
    # ------------------------------------------------------------------------------------------
    def get_post_or_404(self, post_id: Optional[int]) -> SocialPost:
        post = self.db.get(SocialPost, post_id) if post_id else None
        if not post:
            raise not_found_post()
        return post

    def resolve_exercise(self, exercise_id: Optional[int], legacy_ids: bool = False) -> Optional[Exercise]:
        """exercise_id theo đặc tả là id bài viết của GV; legacy_ids=True ưu tiên id bảng exercises (API v1 cũ)."""
        if not exercise_id:
            return None
        by_post = lambda: self.db.query(Exercise).filter(Exercise.post_id == exercise_id).first()
        by_id = lambda: self.db.get(Exercise, exercise_id)
        return (by_id() or by_post()) if legacy_ids else (by_post() or by_id())

    def submission_count(self, exercise: Optional[Exercise], exclude_user: Optional[int] = None) -> int:
        if not exercise:
            return 0
        q = self.db.query(Submission).filter(Submission.exercise_id == exercise.id)
        if exclude_user:
            q = q.filter(Submission.student_id != exclude_user)
        return q.count()

    def is_exercise_post(self, post: SocialPost) -> bool:
        return bool(post.exercise and post.exercise.post_id == post.id)

    # ------------------------------------------------------------------------------------------
    # Đăng bài
    # ------------------------------------------------------------------------------------------
    def add_post(self, user: User, described: Optional[str], left_video=None, right_video=None,
                 course_id: Optional[int] = None, exercise_id: Optional[int] = None,
                 device_master: Optional[str] = None, device_slave: Optional[str] = None,
                 legacy_ids: bool = False) -> SocialPost:
        described = (described or "").strip()
        if exceeds_word_limit(described, settings.MAX_WORDS):
            raise param_invalid(f"Nội dung bài viết vượt quá {settings.MAX_WORDS} từ.")
        if not described and not left_video and not right_video:
            raise param_missing("described hoặc video")

        exercise = self.resolve_exercise(exercise_id, legacy_ids) if exercise_id else None
        if exercise_id and not exercise:
            raise ApiError("9992", "Bài tập không tồn tại.", 404)
        if exercise and not (left_video or right_video):
            raise param_missing("left_video/right_video (bài nộp cần ít nhất 01 video)")

        is_coach = user.role == UserRole.COACH
        course: Optional[Course] = None
        if exercise:
            course = exercise.course or self.courses.get_by_spec_id(course_id)
            if (user.role == UserRole.STUDENT and exercise.course_id
                    and not self.courses.is_approved_member(exercise.course_id, user.id)):
                raise no_access("Bạn cần tham gia khóa học (được GV duyệt) trước khi nộp bài.")
        elif is_coach:
            course = self.courses.ensure_course(user)
        elif course_id:
            course = self.courses.get_by_spec_id(course_id)

        prefix = f"post_u{user.id}"
        left_url = video_service.save_video_upload(left_video, prefix + "_left") if left_video else None
        right_url = video_service.save_video_upload(right_video, prefix + "_right") if right_video else None
        fused_url = video_service.merge_videos(left_url, right_url, prefix) if left_url and right_url else None

        post = SocialPost(
            user_id=user.id, content=described, course_id=course.id if course else None,
            exercise_id=exercise.id if exercise else None,
            video_left_url=left_url, video_right_url=right_url, video_fused_url=fused_url,
            thumbnail_url=video_service.make_thumbnail(left_url or right_url),
            device_master=device_master, device_slave=device_slave, likes_count=0, edited_times=0,
        )
        self.db.add(post)
        self.db.commit()
        self.db.refresh(post)

        if exercise:
            # Bài nộp của HV: hashtag khóa học & bài tập tự động điền (Slide 6)
            course_tag = course.teacher_id if course and not legacy_ids else (course_id or (course.teacher_id if course else None))
            post.content = self._with_hashtags(described, course_tag, exercise_id)
            self.db.commit()
            if is_coach and exercise.created_by != user.id:
                # GV không làm bài tập của GV khác: đăng được nhưng không chấm (Slide 28)
                logger.info("GV %s nộp bài tập của GV khác - không chấm điểm", user.id)
            elif not is_coach or exercise.created_by == user.id:
                from .submission_service import SubmissionService
                submission = SubmissionService(self.db).submit_exercise(
                    exercise_id=exercise.id, student_id=user.id, video_path=left_url or right_url,
                    post_id=post.id, right_video_path=right_url if left_url else None,
                )
                post.submission_id = submission.id
                self.db.commit()
                if exercise.created_by != user.id:
                    self.notifier.notify(exercise.created_by, "submission", "Học viên nộp bài",
                                         f"{user.full_name or user.username} vừa nộp bài tập của bạn.", post.id, user.id)
        elif is_coach and (left_url or right_url):
            # Bài đăng có video của GV = video chuẩn làm đáp án chấm điểm (Slide 5)
            new_ex = Exercise(
                title=(described.splitlines()[0][:150] if described else f"Bài tập #{post.id}") or f"Bài tập #{post.id}",
                category="general", description=described, course_id=course.id if course else None,
                coach_video_url=left_url or right_url, coach_video_right_url=right_url if left_url else None,
                created_by=user.id, post_id=post.id,
            )
            self.db.add(new_ex)
            self.db.commit()
            post.exercise_id = new_ex.id
            # Hashtag khóa học & bài tập chèn vào đầu bài viết của GV (Slide 24)
            post.content = self._with_hashtags(described, user.id, post.id)
            self.db.commit()
            run_in_background(self.background, precompute_exercise_pose, new_ex.id)
            if course:
                student_ids = [m.student_id for m in self.courses.list_students(course, 0, 500)]
                self.notifier.notify_many(student_ids, "new_post", "Bài tập mới",
                                          f"{user.full_name or user.username} vừa đăng bài tập mới.", post.id, user.id)
        elif course and not is_coach:
            post.content = self._with_hashtags(described, course.teacher_id, None)
            self.db.commit()

        self.db.refresh(post)
        return post

    @staticmethod
    def _with_hashtags(text: str, course_tag: Any, exercise_tag: Any) -> str:
        tags = []
        if course_tag and f"#course_{course_tag}" not in text:
            tags.append(f"#course_{course_tag}")
        if exercise_tag and f"#exercise_{exercise_tag}" not in text:
            tags.append(f"#exercise_{exercise_tag}")
        return " ".join(tags + ([text] if text else [])).strip()

    # ------------------------------------------------------------------------------------------
    # Sửa / xóa bài
    # ------------------------------------------------------------------------------------------
    def can_edit(self, post: SocialPost, user: Optional[User]) -> bool:
        if not user or post.user_id != user.id:
            return False
        if user.role == UserRole.COACH and self.is_exercise_post(post):
            return self.submission_count(post.exercise, exclude_user=user.id) == 0
        return True

    def can_delete(self, post: SocialPost, user: Optional[User]) -> bool:
        if not user:
            return False
        if user.role == UserRole.ADMIN:
            return True
        # HV hoàn toàn có thể sửa, xóa bài viết (GV thì không) - Slide 29
        return post.user_id == user.id and user.role != UserRole.COACH

    def edit_post(self, user: User, post_id: int, described: Optional[str] = None, video_indices: Optional[str] = None,
                  left_video=None, right_video=None) -> SocialPost:
        post = self.get_post_or_404(post_id)
        if post.user_id != user.id:
            raise no_access("Không có quyền sửa bài viết của người khác.")
        if user.role == UserRole.COACH and self.is_exercise_post(post) and self.submission_count(post.exercise, user.id) > 0:
            raise ApiError("1010", "Không thể sửa bài tập khi đã có học viên nộp bài.")
        if described is not None and exceeds_word_limit(described, settings.MAX_WORDS):
            raise param_invalid(f"Nội dung bài viết vượt quá {settings.MAX_WORDS} từ.")

        indices = parse_video_indices(video_indices)
        uploads = {"L": left_video, "R": right_video}
        current = {"L": post.video_left_url, "R": post.video_right_url}
        # Video bị thay phải có file thay thế (test case 6, 7)
        for side in indices:
            if not uploads[side]:
                raise param_missing(f"{'left_video' if side == 'L' else 'right_video'} để thay thế video bị xóa")
        apply: Dict[str, Any] = {}
        for side, upload in uploads.items():
            if not upload:
                continue
            if side in indices or not current[side]:
                apply[side] = upload  # thay video được chỉ định, hoặc bổ sung video vào bên còn trống
            # còn lại: upload mà không nói rõ video nào bị thay -> bỏ qua (test case 8, 9)
        text_changed = described is not None and described.strip() != (post.content or "")
        if not apply and not text_changed:
            raise param_invalid("Không có thông tin hợp lệ để cập nhật (cần chỉ rõ video_indices cho video bị thay).")

        prefix = f"post_u{user.id}"
        for side, upload in apply.items():
            url = video_service.save_video_upload(upload, f"{prefix}_{'left' if side == 'L' else 'right'}")
            if side == "L":
                post.video_left_url = url
            else:
                post.video_right_url = url
        if apply:
            post.video_fused_url = (video_service.merge_videos(post.video_left_url, post.video_right_url, prefix)
                                    if post.video_left_url and post.video_right_url else None)
            post.thumbnail_url = video_service.make_thumbnail(post.video_left_url or post.video_right_url)
        if text_changed:
            if self.is_exercise_post(post):
                post.content = self._with_hashtags(described.strip(), user.id, post.id)
            elif post.exercise:
                tag = post.exercise.course.teacher_id if post.exercise.course else None
                post.content = self._with_hashtags(described.strip(), tag, post.exercise.post_id or post.exercise.id)
            else:
                post.content = described.strip()
        post.edited_times = (post.edited_times or 0) + 1

        if apply and self.is_exercise_post(post):
            ex = post.exercise
            ex.coach_video_url = post.video_left_url or post.video_right_url
            ex.coach_video_right_url = post.video_right_url if post.video_left_url else None
            ex.coach_pose_cache_url = None
            self.db.commit()
            run_in_background(self.background, precompute_exercise_pose, ex.id)
        # Sửa video bài nộp không chấm lại, điểm cũ giữ nguyên (FAQ Q9)
        self.db.commit()
        self.db.refresh(post)
        return post

    def delete_post(self, user: User, post_id: int) -> None:
        post = self.get_post_or_404(post_id)
        if not self.can_delete(post, user):
            raise no_access("Giáo viên không được xóa bài viết; chỉ chủ bài viết là học viên mới xóa được.")
        if post.exercise and post.exercise.post_id == post.id:
            post.exercise.post_id = None
        self.db.query(Exercise).filter(Exercise.post_id == post.id).update({Exercise.post_id: None})
        self.db.delete(post)
        self.db.commit()

    # ------------------------------------------------------------------------------------------
    # Hiển thị
    # ------------------------------------------------------------------------------------------
    def serialize(self, post: SocialPost, viewer: Optional[User], detail: bool = False,
                  include_comments: bool = False) -> Dict[str, Any]:
        author = post.author or self.db.get(User, post.user_id)
        ex = post.exercise
        is_exercise = bool(ex and ex.post_id == post.id)
        comment_count = self.db.query(func.count(Comment.id)).filter(Comment.post_id == post.id).scalar() or 0
        is_liked = bool(viewer and self.db.query(PostLike).filter(
            PostLike.post_id == post.id, PostLike.user_id == viewer.id).first())
        videos = []
        for side, url in (("left", post.video_left_url), ("right", post.video_right_url)):
            if url:
                videos.append({"side": side, "url": url, "thumb": post.thumbnail_url})
        sub = self.db.get(Submission, post.submission_id) if post.submission_id else None
        lecturer = None
        exercise_spec_id = None
        course_spec_id = None
        if ex:
            exercise_spec_id = ex.post_id or ex.id
            course_spec_id = ex.course.teacher_id if ex.course else None
            if not is_exercise and ex.coach and ex.coach.id != post.user_id:
                lecturer = user_brief(ex.coach)
        elif post.course:
            course_spec_id = post.course.teacher_id
        data = {
            "id": post.id,
            "post_id": post.id,
            "user_id": post.user_id,
            "described": post.content,
            "content": post.content,
            "created": iso(post.created_at),
            "created_at": iso(post.created_at),
            "modified": iso(post.updated_at),
            "updated_at": iso(post.updated_at),
            "like": post.likes_count or 0,
            "likes_count": post.likes_count or 0,
            "comment": comment_count,
            "comments_count": comment_count,
            "is_liked": is_liked,
            "video": videos,
            "video_left_url": post.video_left_url,
            "video_right_url": post.video_right_url,
            "video_fused_url": post.video_fused_url,
            "thumbnail_url": post.thumbnail_url,
            "device_master": post.device_master,
            "device_slave": post.device_slave,
            "author": user_brief(author),
            "lecturer": lecturer,
            "course_id": course_spec_id,
            "exercise_id": exercise_spec_id,
            "internal_course_id": post.course_id,
            "internal_exercise_id": post.exercise_id,
            "is_exercise": is_exercise,
            "submission_id": post.submission_id,
            "submission": submission_brief(sub),
            "edited_times": post.edited_times or 0,
            "is_blocked": bool(viewer and self.rel.has_blocked(post.user_id, viewer.id)),
            "can_edit": self.can_edit(post, viewer),
            "can_delete": self.can_delete(post, viewer),
            "can_submit": bool(is_exercise and viewer and viewer.role == UserRole.STUDENT),
            "banned": bool(author and not author.is_active),
        }
        if is_exercise:
            data["submissions_count"] = self.submission_count(ex)
        if detail and is_exercise:
            data["time_series_poses"] = self._time_series(ex)
        if include_comments:
            data["comments"] = [self.serialize_comment(c, viewer) for c in self._visible_comments(post.id, viewer, 0, 100)]
        return data

    @staticmethod
    def _time_series(ex: Exercise) -> Optional[List[Dict[str, Any]]]:
        if not ex.coach_pose_cache_url:
            return None
        path = video_service.to_fs(ex.coach_pose_cache_url)
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def _visible_post_query(self, viewer: Optional[User]):
        q = self.db.query(SocialPost)
        hidden = self.rel.hidden_user_ids(viewer.id if viewer else None)
        if hidden:
            q = q.filter(~SocialPost.user_id.in_(hidden))
        return q

    def list_posts(self, viewer: Optional[User], index: int = 0, count: int = 20, user_id: Optional[int] = None,
                   last_id: Optional[int] = None, only_exercises: bool = False) -> Dict[str, Any]:
        """
        Slide 27: HV đăng nhập thấy ưu tiên bài của khóa học đã đăng ký, sau đó tới bài của người khác;
        sắp xếp theo thời gian, không hiển thị bài của người bị chặn.
        """
        if user_id and viewer and self.rel.is_blocked_between(viewer.id, user_id):
            raise no_access("Không thể xem trang của người dùng này.")
        q = self._visible_post_query(viewer)
        if user_id:
            q = q.filter(SocialPost.user_id == user_id)
        if only_exercises:
            q = q.filter(SocialPost.id.in_(self.db.query(Exercise.post_id).filter(Exercise.post_id.isnot(None))))
        order = (SocialPost.created_at.desc(), SocialPost.id.desc())
        ids: List[int]
        if viewer and viewer.role == UserRole.STUDENT and not user_id:
            course_ids = self.courses.approved_course_ids(viewer.id)
            teacher_ids = {c.teacher_id for c in self.db.query(Course).filter(Course.id.in_(course_ids)).all()} if course_ids else set()
            # coalesce: bài không thuộc khóa nào (course_id NULL) vẫn nằm ở nhóm "bài khác" thay vì bị NULL loại mất
            priority_filter = (func.coalesce(SocialPost.course_id, -1).in_(course_ids)
                               | SocialPost.user_id.in_(teacher_ids)) if course_ids else None
            if priority_filter is not None:
                first = [p.id for p in q.filter(priority_filter).order_by(*order).with_entities(SocialPost.id)]
                rest = [p.id for p in q.filter(~priority_filter).order_by(*order).with_entities(SocialPost.id)]
                ids = first + rest
            else:
                ids = [p.id for p in q.order_by(*order).with_entities(SocialPost.id)]
        else:
            ids = [p.id for p in q.order_by(*order).with_entities(SocialPost.id)]
        page_ids = ids[index:index + count]
        posts = {p.id: p for p in self.db.query(SocialPost).filter(SocialPost.id.in_(page_ids)).all()} if page_ids else {}
        items = [self.serialize(posts[i], viewer) for i in page_ids if i in posts]
        new_items = len([i for i in ids if last_id and i > last_id]) if last_id else 0
        return {"posts": items, "new_items": new_items, "last_id": max(ids) if ids else 0, "total": len(ids)}

    def get_post(self, viewer: Optional[User], post_id: int) -> Dict[str, Any]:
        post = self.get_post_or_404(post_id)
        if viewer and self.rel.is_blocked_between(viewer.id, post.user_id):
            raise no_access("Bạn không thể xem bài viết này.")
        return self.serialize(post, viewer, detail=True)

    def check_new_items(self, viewer: Optional[User], last_id: int) -> int:
        return self._visible_post_query(viewer).filter(SocialPost.id > last_id).count()

    # ------------------------------------------------------------------------------------------
    # Like / báo cáo
    # ------------------------------------------------------------------------------------------
    def toggle_like(self, user: User, post_id: int) -> Tuple[bool, int]:
        post = self.get_post_or_404(post_id)
        if self.rel.is_blocked_between(user.id, post.user_id):
            raise no_access("Không thể tương tác với bài viết này.")
        existing = self.db.query(PostLike).filter(PostLike.post_id == post.id, PostLike.user_id == user.id).first()
        if existing:
            self.db.delete(existing)
            liked = False
        else:
            self.db.add(PostLike(post_id=post.id, user_id=user.id))
            liked = True
        self.db.flush()
        post.likes_count = self.db.query(PostLike).filter(PostLike.post_id == post.id).count()
        self.db.commit()
        if liked:
            self.notifier.notify(post.user_id, "like", "Lượt thích mới",
                                 f"{user.full_name or user.username} đã thích bài viết của bạn.", post.id, user.id)
        return liked, post.likes_count

    def report(self, user: User, post_id: int, subject: str, details: Optional[str]) -> None:
        post = self.get_post_or_404(post_id)
        if self.db.query(PostReport).filter(PostReport.post_id == post.id, PostReport.user_id == user.id).first():
            raise ApiError("1010", "Bạn đã báo cáo bài viết này trước đó.")
        self.db.add(PostReport(post_id=post.id, user_id=user.id, subject=subject.strip()[:200], details=details))
        self.db.commit()

    # ------------------------------------------------------------------------------------------
    # Bình luận
    # ------------------------------------------------------------------------------------------
    def _visible_comments(self, post_id: int, viewer: Optional[User], index: int, count: int) -> List[Comment]:
        q = self.db.query(Comment).filter(Comment.post_id == post_id)
        hidden = self.rel.hidden_user_ids(viewer.id if viewer else None)
        if hidden:
            # A chặn B: bình luận của B không bị xóa nhưng A không thấy (Slide 26)
            q = q.filter((Comment.user_id.is_(None)) | (~Comment.user_id.in_(hidden)))
        return q.order_by(Comment.created_at.asc(), Comment.id.asc()).offset(index).limit(count).all()

    def serialize_comment(self, c: Comment, viewer: Optional[User]) -> Dict[str, Any]:
        poster = user_brief(c.user) if c.user else {"id": None, "username": "AI Auto-Scorer", "name": "AI Auto-Scorer",
                                                     "avatar": None, "role": "bot", "role_label": "BOT"}
        return {
            "id": c.id, "post_id": c.post_id, "user_id": c.user_id,
            "comment": c.content, "content": c.content,
            "created": iso(c.created_at), "created_at": iso(c.created_at),
            "poster": poster, "user": poster,
            "is_bot_evaluation": bool(c.is_bot_evaluation),
            "score": c.score, "detail_mistakes": c.detail_mistakes,
            "is_blocked": bool(viewer and c.user_id and self.rel.has_blocked(c.user_id, viewer.id)),
        }

    def get_comments(self, viewer: Optional[User], post_id: int, index: int = 0, count: int = 50) -> List[Dict[str, Any]]:
        post = self.get_post_or_404(post_id)
        if viewer and self.rel.is_blocked_between(viewer.id, post.user_id):
            raise no_access("Bạn không thể xem bài viết này.")
        return [self.serialize_comment(c, viewer) for c in self._visible_comments(post.id, viewer, index, count)]

    def set_comment(self, user: User, post_id: int, comment: Optional[str], score: Optional[float] = None,
                    detail_mistakes: Optional[str] = None, index: int = 0, count: int = 50) -> List[Dict[str, Any]]:
        post = self.get_post_or_404(post_id)
        if self.rel.is_blocked_between(user.id, post.user_id):
            raise no_access("Không thể bình luận bài viết này.")
        is_bot = user.role == UserRole.ADMIN and (score is not None or detail_mistakes)
        if (score is not None or detail_mistakes) and not is_bot:
            raise no_access("Chỉ tài khoản chấm điểm (admin/AI bot) mới được gửi score và detail_mistakes.")
        text = comment if is_bot else sanitize_comment(comment or "")
        if not text and not is_bot:
            raise param_missing("comment")
        if exceeds_word_limit(text, settings.MAX_WORDS):
            raise param_invalid(f"Bình luận vượt quá {settings.MAX_WORDS} từ.")
        if score is not None and not (0 <= score <= 100):
            raise param_invalid("Điểm số phải trong khoảng 0 - 100.")
        c = Comment(post_id=post.id, user_id=user.id, content=text or f"Điểm: {score}", is_bot_evaluation=bool(is_bot),
                    score=score, detail_mistakes=detail_mistakes)
        self.db.add(c)
        self.db.commit()
        self.notifier.notify(post.user_id, "comment", "Bình luận mới",
                             f"{user.full_name or user.username}: {text[:80]}", post.id, user.id)
        return self.get_comments(user, post.id, index, count)

    # ------------------------------------------------------------------------------------------
    # Tìm kiếm (Slide 31: "Nga thiên hồ múa" vẫn tìm ra "múa Hồ Thiên Nga")
    # ------------------------------------------------------------------------------------------
    def search(self, viewer: Optional[User], keyword: str, user_id: Optional[int] = None,
               index: int = 0, count: int = 20, save: bool = True) -> List[Dict[str, Any]]:
        tokens = search_tokens(keyword or "")
        if not tokens:
            raise param_missing("keyword")
        q = self._visible_post_query(viewer)
        if user_id:
            q = q.filter(SocialPost.user_id == user_id)
        matches = []
        for post in q.order_by(SocialPost.created_at.desc()).all():
            author = post.author
            hay = f"{post.content or ''} {author.username if author else ''} {author.full_name or '' if author else ''}"
            if matches_all_tokens(hay, tokens):
                matches.append(post)
        if save and viewer:
            last = self.db.query(SavedSearch).filter(SavedSearch.user_id == viewer.id).order_by(SavedSearch.id.desc()).first()
            if not last or last.keyword != keyword.strip():
                self.db.add(SavedSearch(user_id=viewer.id, keyword=keyword.strip()[:200]))
                self.db.commit()
        return [self.serialize(p, viewer) for p in matches[index:index + count]]

    def saved_searches(self, user: User, index: int, count: int) -> List[SavedSearch]:
        return (self.db.query(SavedSearch).filter(SavedSearch.user_id == user.id)
                .order_by(SavedSearch.id.desc()).offset(index).limit(count).all())

    def delete_saved_search(self, user: User, search_id: Optional[int], delete_all: bool) -> None:
        q = self.db.query(SavedSearch).filter(SavedSearch.user_id == user.id)
        if not delete_all:
            if not search_id:
                raise param_missing("search_id")
            q = q.filter(SavedSearch.id == search_id)
            if not q.first():
                raise ApiError("9994", "Không tìm thấy lịch sử tìm kiếm.", 404)
        q.delete(synchronize_session=False)
        self.db.commit()

# ----------------------------------------------------------------------------------------------
# Tác vụ nền: trích xuất pose 3D của video HLV ngay khi GV đăng bài (server lưu pose3D của thầy - Slide 8)
# ----------------------------------------------------------------------------------------------
def precompute_exercise_pose(exercise_id: int) -> None:
    from ..core.database import SessionLocal
    from ai_engine.factory import AIEngineFactory
    db = SessionLocal()
    try:
        ex = db.get(Exercise, exercise_id)
        if not ex:
            return
        pipeline = AIEngineFactory.create_pipeline_from_settings(settings)
        pose = pipeline.extract(video_service.to_fs(ex.coach_video_url), use_cache=True)
        if ex.coach_video_right_url:
            pipeline.extract(video_service.to_fs(ex.coach_video_right_url), use_cache=True)
        frames = time_series_from_pose(pose, per_second=4)
        os.makedirs(settings.POSE_CACHE_DIR, exist_ok=True)
        out = os.path.join(settings.POSE_CACHE_DIR, f"exercise_{ex.id}_time_series.json")
        with open(out, "w", encoding="utf-8") as f:
            json.dump(frames, f, ensure_ascii=False)
        ex.coach_pose_cache_url = video_service.to_url(out)
        db.commit()
    except Exception as e:
        logger.warning("Không trích xuất được pose HLV cho bài tập %s: %s", exercise_id, e)
    finally:
        db.close()

def time_series_from_pose(pose: Dict[str, Any], per_second: int = 4) -> List[Dict[str, Any]]:
    """Định dạng time_series_poses của get_post: 4 frame/giây, mỗi frame gồm danh sách điểm pose."""
    joints = pose.get("joints_3d")
    if joints is None:
        return []
    names = pose.get("joint_names") or [f"joint_{i}" for i in range(joints.shape[1])]
    fps = float(pose.get("fps") or 30.0)
    step = max(1, int(round(fps / per_second)))
    frame_idx = pose.get("frame_indices") or list(range(len(joints)))
    out = []
    for i in range(0, len(joints), step):
        out.append({
            "frame_id": int(frame_idx[i]) if i < len(frame_idx) else i,
            "created": round(i / fps, 3),
            "poses": [
                {"pose_name": names[j], "pose_coord": {"x": round(float(p[0]), 4), "y": round(float(p[1]), 4), "z": round(float(p[2]), 4)}}
                for j, p in enumerate(joints[i])
            ],
        })
    return out
