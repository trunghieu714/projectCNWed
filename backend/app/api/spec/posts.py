"""Nhóm API bài viết: add_post, edit_post, delete_post, get_post, get_list_posts, get_comment,
set_comment, like, report_post, search, get_saved_search, del_saved_search, check_new_item, get_submission,
set_grading_result / get_grading_result (gửi / tải file zip kết quả chấm - Slide 8)."""
import json
import os

from fastapi import APIRouter, BackgroundTasks, Depends

from ...core.errors import ApiError, no_access, ok, param_invalid, param_missing
from ...models.entities import SocialPost, Submission, UserRole
from ...services.grading_result import MAX_ZIP_BYTES, REPORT_NAME, SKELETON_NAME, apply_result_zip, ensure_result_zip
from ...services.post_service import PostService
from ...services.serializers import iso, submission_brief
from ...services.video_service import to_url
from .params import Ctx, get_ctx

router = APIRouter()

@router.post("/add_post")
def add_post(background: BackgroundTasks, ctx: Ctx = Depends(get_ctx)):
    """
    Input: token, left_video, right_video (có thể chỉ 1 video), course_id, exercise_id, described,
    device_slave, device_master. HV nộp bài: exercise_id = id bài viết của GV, course_id = id GV.
    """
    p = ctx.p
    post = PostService(ctx.db, background).add_post(
        ctx.user, p.str("described"), p.file("left_video"), p.file("right_video"),
        course_id=p.int("course_id"), exercise_id=p.int("exercise_id"),
        device_master=p.str("device_master", max_len=100), device_slave=p.str("device_slave", max_len=100),
    )
    return ok({"id": post.id, "url": f"/posts/{post.id}", "submission_id": post.submission_id,
               "described": post.content, "exercise_id": post.exercise.post_id if post.exercise else None},
              "Đăng bài thành công.")

@router.post("/edit_post")
def edit_post(background: BackgroundTasks, ctx: Ctx = Depends(get_ctx)):
    """Input: token, id, described, video_indices (L | R | LR | all), left_video, right_video."""
    p = ctx.p
    post = PostService(ctx.db, background).edit_post(
        ctx.user, p.int("id", required=True), described=p.str("described"), video_indices=p.str("video_indices"),
        left_video=p.file("left_video"), right_video=p.file("right_video"),
    )
    return ok({"id": post.id, "url": f"/posts/{post.id}", "edited_times": post.edited_times}, "Sửa bài thành công.")

@router.post("/delete_post")
@router.post("/del_post")
def delete_post(ctx: Ctx = Depends(get_ctx)):
    PostService(ctx.db).delete_post(ctx.user, ctx.p.int("id", required=True))
    return ok(None, "Xóa bài thành công.")

@router.post("/get_post")
def get_post(ctx: Ctx = Depends(get_ctx)):
    return ok(PostService(ctx.db).get_post(ctx.optional_user, ctx.p.int("id", required=True)))

@router.post("/get_list_posts")
def get_list_posts(ctx: Ctx = Depends(get_ctx)):
    index, count = ctx.p.page()
    data = PostService(ctx.db).list_posts(ctx.optional_user, index, count, user_id=ctx.p.int("user_id"),
                                          last_id=ctx.p.int("last_id"), only_exercises=ctx.p.flag("only_exercises"))
    if not data["posts"] and index > 0:
        raise ApiError("9994", "Không còn dữ liệu.", 200, data)
    return ok(data)

@router.post("/check_new_item")
@router.post("/check_new_items")
def check_new_item(ctx: Ctx = Depends(get_ctx)):
    return ok({"new_items": PostService(ctx.db).check_new_items(ctx.optional_user, ctx.p.int("last_id", default=0))})

@router.post("/get_comment")
def get_comment(ctx: Ctx = Depends(get_ctx)):
    index, count = ctx.p.page(50)
    return ok(PostService(ctx.db).get_comments(ctx.optional_user, ctx.p.int("id", required=True), index, count))

@router.post("/set_comment")
def set_comment(ctx: Ctx = Depends(get_ctx)):
    """Input: token, id, comment, index, count, score (tùy chọn), detail_mistakes (xâu HTML, tùy chọn)."""
    index, count = ctx.p.page(50)
    data = PostService(ctx.db).set_comment(
        ctx.user, ctx.p.int("id", required=True), ctx.p.str("comment"), score=ctx.p.float("score"),
        detail_mistakes=ctx.p.str("detail_mistakes"), index=index, count=count)
    return ok(data)

@router.post("/like")
@router.post("/like_post")
def like(ctx: Ctx = Depends(get_ctx)):
    liked, count = PostService(ctx.db).toggle_like(ctx.user, ctx.p.int("id", required=True))
    return ok({"like": count, "is_liked": liked})

@router.post("/report_post")
def report_post(ctx: Ctx = Depends(get_ctx)):
    PostService(ctx.db).report(ctx.user, ctx.p.int("id", required=True), ctx.p.str("subject", required=True, max_len=200),
                               ctx.p.str("details"))
    return ok(None, "Đã gửi báo cáo.")

@router.post("/search")
def search(ctx: Ctx = Depends(get_ctx)):
    index, count = ctx.p.page()
    return ok(PostService(ctx.db).search(ctx.optional_user, ctx.p.str("keyword", required=True, max_len=200),
                                         user_id=ctx.p.int("user_id"), index=index, count=count))

@router.post("/get_saved_search")
def get_saved_search(ctx: Ctx = Depends(get_ctx)):
    index, count = ctx.p.page()
    rows = PostService(ctx.db).saved_searches(ctx.user, index, count)
    return ok([{"id": r.id, "keyword": r.keyword, "created": iso(r.created_at)} for r in rows])

@router.post("/del_saved_search")
def del_saved_search(ctx: Ctx = Depends(get_ctx)):
    PostService(ctx.db).delete_saved_search(ctx.user, ctx.p.int("search_id"), ctx.p.flag("all"))
    return ok(None)

@router.post("/get_submission")
def get_submission(ctx: Ctx = Depends(get_ctx)):
    """Chi tiết kết quả chấm (điểm từng góc quay, warping path, đoạn lỗi) cho trang xem kết quả."""
    user = ctx.user
    sub = ctx.db.get(Submission, ctx.p.int("id", required=True))
    if not sub:
        raise ApiError("9994", "Không tìm thấy bài nộp.", 404)
    exercise = sub.exercise
    if user.id != sub.student_id and user.role != UserRole.ADMIN and (not exercise or exercise.created_by != user.id):
        raise no_access()
    data = submission_brief(sub)
    data["detail"] = json.loads(sub.result_json) if sub.result_json else None
    data["coach_video_url"] = exercise.coach_video_url if exercise else None
    data["coach_video_right_url"] = exercise.coach_video_right_url if exercise else None
    data["student_video_right_url"] = sub.student_video_right_url
    data["exercise_title"] = exercise.title if exercise else None
    data["post_id"] = sub.post.id if sub.post else None
    return ok(data)

def _submission_post(ctx: Ctx) -> SocialPost:
    post = ctx.db.get(SocialPost, ctx.p.int("id", required=True))
    if not post:
        raise ApiError("9992", "Bài viết không tồn tại.", 404)
    if not post.submission:
        raise param_invalid("Bài viết này không phải bài nộp của học viên.")
    return post

@router.post("/set_grading_result")
def set_grading_result(ctx: Ctx = Depends(get_ctx)):
    """
    Slide 8: phần mềm chấm (PC có GPU / Colab) gửi file zip kết quả lên server.
    Input: token (GV ra bài tập hoặc admin), id (bài nộp của HV), result (file zip: report.html, result.json
    có score 0-100, tùy chọn fused.mp4). Thay bình luận điểm cũ của bot bằng kết quả mới.
    """
    user = ctx.user
    post = _submission_post(ctx)
    exercise = post.submission.exercise
    if user.role != UserRole.ADMIN and (not exercise or exercise.created_by != user.id):
        raise no_access("Chỉ giáo viên ra bài tập hoặc quản trị viên được gửi kết quả chấm.")
    upload = ctx.p.file("result")
    if upload is None:
        raise param_missing("result")
    data = upload.file.read(MAX_ZIP_BYTES + 1)
    return ok(apply_result_zip(ctx.db, post, data), "Đã cập nhật kết quả chấm.")

@router.post("/get_grading_result")
def get_grading_result(ctx: Ctx = Depends(get_ctx)):
    """Link tải result.zip (report.html + result.json + video ghép) của một bài nộp. Input: token, id (bài nộp)."""
    user = ctx.user
    post = _submission_post(ctx)
    sub = post.submission
    exercise = sub.exercise
    if user.id != sub.student_id and user.role != UserRole.ADMIN and (not exercise or exercise.created_by != user.id):
        raise no_access()
    path = ensure_result_zip(sub)
    if not path:
        raise ApiError("9994", "Bài nộp chưa có kết quả chấm.")
    report = os.path.join(os.path.dirname(path), REPORT_NAME)
    skeleton = os.path.join(os.path.dirname(path), SKELETON_NAME)
    return ok({"id": post.id, "submission_id": sub.id, "score": sub.score, "url": to_url(path),
               "size": os.path.getsize(path), "report_url": to_url(report) if os.path.isfile(report) else None,
               "skeleton_url": to_url(skeleton) if os.path.isfile(skeleton) else None})
