from typing import List, Optional, Dict, Any
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from ....core.config import settings
from ....core.database import get_db
from ....core.text_rules import exceeds_word_limit
from ....models.entities import User
from ....schemas.post import PostCreate
from ....schemas.comment import CommentCreate
from ....schemas.response import ApiResponse, ErrorCodes
from ....repositories.social_repository import SocialRepository
from ....services.post_service import PostService
from ...deps import get_current_user, get_optional_user

router = APIRouter()

@router.get("/")
def get_community_feed(
    skip: int = 0,
    limit: int = 30,
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    """Bản tin: ưu tiên bài của khóa học đã đăng ký, ẩn bài của người bị chặn (Slide 27)."""
    service = PostService(db)
    data = service.list_posts(current_user, index=skip, count=limit)
    return data["posts"]

@router.post("/", status_code=status.HTTP_201_CREATED)
def create_post(
    post_in: PostCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Đăng bài văn bản (chia sẻ kinh nghiệm hoặc đính kèm kết quả bài nộp)."""
    if exceeds_word_limit(post_in.content, settings.MAX_WORDS):
        raise HTTPException(status_code=400, detail={"code": ErrorCodes.PARAMETER_VALUE_INVALID,
                                                     "message": f"Nội dung vượt quá {settings.MAX_WORDS} từ."})
    repo = SocialRepository(db)
    post = repo.create(
        user_id=current_user.id,
        content=post_in.content,
        submission_id=post_in.submission_id,
        course_id=post_in.course_id,
        exercise_id=post_in.exercise_id,
        video_left_url=post_in.video_left_url,
        video_right_url=post_in.video_right_url,
        video_fused_url=post_in.video_fused_url
    )
    return PostService(db).serialize(post, current_user)

@router.post("/add_post", response_model=ApiResponse[Dict[str, Any]], status_code=status.HTTP_201_CREATED)
def add_post_multipart(
    background: BackgroundTasks,
    described: Optional[str] = Form(None),
    course_id: Optional[int] = Form(None),
    exercise_id: Optional[int] = Form(None),
    device_master: Optional[str] = Form(None),
    device_slave: Optional[str] = Form(None),
    left_video: Optional[UploadFile] = File(None),
    right_video: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    API add_post (Slide 6 & Slide 40 Tuần 2) - phiên bản REST, dùng chung nghiệp vụ với POST /api/add_post.
    exercise_id ở API v1 là id bảng exercises (API theo đặc tả dùng id bài viết của GV).
    """
    post = PostService(db, background).add_post(
        current_user, described, left_video, right_video, course_id=course_id, exercise_id=exercise_id,
        device_master=device_master, device_slave=device_slave, legacy_ids=True,
    )
    return ApiResponse(
        code=ErrorCodes.OK,
        message="Đăng bài thành công.",
        data={
            "id": post.id,
            "submission_id": post.submission_id,
            "content": post.content,
            "video_left_url": post.video_left_url,
            "video_right_url": post.video_right_url,
            "video_fused_url": post.video_fused_url,
            "created_at": str(post.created_at)
        }
    )

@router.post("/{post_id}/edit_post", response_model=ApiResponse[Dict[str, Any]])
def edit_post(
    post_id: int,
    background: BackgroundTasks,
    described: Optional[str] = Form(None),
    video_indices: Optional[str] = Form(None),
    left_video: Optional[UploadFile] = File(None),
    right_video: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """API edit_post (Slide 7 & Slide 35-41 Tuần 3): video_indices = L | R | LR chỉ rõ video bị thay."""
    post = PostService(db, background).edit_post(current_user, post_id, described, video_indices, left_video, right_video)
    return ApiResponse(
        code=ErrorCodes.OK,
        message="Chỉnh sửa bài viết thành công.",
        data={
            "id": post.id,
            "content": post.content,
            "video_left_url": post.video_left_url,
            "video_right_url": post.video_right_url,
            "video_fused_url": post.video_fused_url,
            "edited_times": post.edited_times,
            "updated_at": str(post.updated_at)
        }
    )

@router.delete("/{post_id}", response_model=ApiResponse[Dict[str, Any]])
def delete_post(post_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    PostService(db).delete_post(current_user, post_id)
    return ApiResponse(code=ErrorCodes.OK, message="Xóa bài thành công.", data={"id": post_id})

@router.post("/{post_id}/comments", response_model=ApiResponse[Dict[str, Any]], status_code=status.HTTP_201_CREATED)
def create_comment(
    post_id: int,
    comment_in: CommentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Người dùng bình luận vào bài viết (tối đa 500 từ, chỉ văn bản / link / emoticon)."""
    comments = PostService(db).set_comment(current_user, post_id, comment_in.content, index=0, count=500)
    mine = [c for c in comments if c["user_id"] == current_user.id]
    return ApiResponse(code=ErrorCodes.OK, message="Bình luận thành công.", data=mine[-1] if mine else None)

@router.get("/{post_id}/comments", response_model=ApiResponse[List[Dict[str, Any]]])
def get_comments(
    post_id: int,
    skip: int = 0,
    limit: int = 50,
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    """Danh sách bình luận (gồm bình luận chấm điểm của AI Bot)."""
    return ApiResponse(code=ErrorCodes.OK, message="OK", data=PostService(db).get_comments(current_user, post_id, skip, limit))

@router.post("/{post_id}/like")
def like_post(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Like / bỏ like (mỗi người chỉ một lượt thích cho mỗi bài)."""
    liked, count = PostService(db).toggle_like(current_user, post_id)
    return {"status": "success", "likes_count": count, "is_liked": liked}
