"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Heart, MessageSquare, Award, Play, User as UserIcon, Share2, Bot, Send, Video, MoreHorizontal, Pencil, Trash2, Flag, Ban, UploadCloud, FileText, Download, Axis3d } from "lucide-react";
import { Post, CommentItem } from "../../types/post";
import { postService } from "../../services/apiClient";
import { call, errorMessage, mediaUrl } from "../../services/api";
import { emojify } from "../../lib/emoticons";
import { useAuth } from "../../hooks/useAuth";
import { Modal, ReportFrame } from "../common/ui";
import { Skeleton3DViewer } from "../player/Skeleton3DViewer";
import { VideoPostModal } from "./VideoPostModal";

interface PostCardProps {
  post: Post;
  /** Gọi khi bài bị xóa hoặc tác giả bị chặn (để danh sách bỏ bài này đi) */
  onRemoved?: (postId: number) => void;
}

const PREVIEW_CHARS = 280;
const REPORT_SUBJECTS = ["Nội dung không phù hợp", "Spam", "Bạo lực", "Thông tin sai sự thật", "Khác"];

export const PostCard: React.FC<PostCardProps> = ({ post: initialPost, onRemoved }) => {
  const router = useRouter();
  const { isAuthenticated, tokenData } = useAuth();
  const [post, setPost] = useState<Post>(initialPost);
  const [likesCount, setLikesCount] = useState<number>(initialPost.likes_count);
  const [isLiked, setIsLiked] = useState<boolean>(!!initialPost.is_liked);
  const [showComments, setShowComments] = useState<boolean>(true);
  const [comments, setComments] = useState<CommentItem[]>(initialPost.comments || []);
  const [newComment, setNewComment] = useState<string>("");
  const [isSendingComment, setIsSendingComment] = useState<boolean>(false);
  const [expanded, setExpanded] = useState<boolean>(false);
  const [menuOpen, setMenuOpen] = useState<boolean>(false);
  const [modal, setModal] = useState<"submit" | "edit" | "report" | null>(null);
  const [reportSubject, setReportSubject] = useState<string>(REPORT_SUBJECTS[0]);
  const [reportDetails, setReportDetails] = useState<string>("");
  const [detailHtml, setDetailHtml] = useState<string | null>(null);
  const [skeletonUrl, setSkeletonUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setPost(initialPost);
    setLikesCount(initialPost.likes_count);
    setIsLiked(!!initialPost.is_liked);
    if (initialPost.comments) setComments(initialPost.comments);
  }, [initialPost]);

  // Bài lấy từ API theo đặc tả không kèm bình luận -> tải riêng
  useEffect(() => {
    if (initialPost.comments) return;
    call<any[]>("get_comment", { id: initialPost.id, index: 0, count: 100 })
      .then((list) => setComments(list.map((c) => ({ ...c, content: c.comment ?? c.content, created_at: c.created ?? c.created_at }))))
      .catch(() => {});
  }, [initialPost.id, initialPost.comments]);

  const requireLogin = () => {
    if (!isAuthenticated) router.push("/login");
    return isAuthenticated;
  };

  const handleLike = async () => {
    if (!requireLogin()) return;
    try {
      const res = await postService.likePost(post.id);
      setLikesCount(res.likes_count);
      setIsLiked((res as any).is_liked ?? !isLiked);
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  const handleSendComment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newComment.trim() || isSendingComment) return;
    if (newComment.trim().split(/\s+/).length > 500) {
      setError("Bình luận vượt quá 500 từ.");
      return;
    }

    setIsSendingComment(true);
    try {
      const cmt = await postService.addComment(post.id, newComment.trim());
      setComments((prev) => [...prev, cmt]);
      setNewComment("");
      setError(null);
    } catch (err: any) {
      setError(err?.response?.data?.message || err?.response?.data?.detail?.message || "Gửi bình luận thất bại.");
    } finally {
      setIsSendingComment(false);
    }
  };

  const reload = async () => {
    try {
      setPost(await call<Post>("get_post", { id: post.id }));
    } catch {}
  };

  // Slide 8: tải result.zip (report.html + result.json + video ghép) của bài nộp
  const downloadResultZip = async () => {
    const tab = window.open("", "_blank");   // mở tab ngay trong lúc click để không bị chặn popup
    try {
      const res = await call<{ url: string }>("get_grading_result", { id: post.id });
      if (tab) tab.location.href = mediaUrl(res.url);
      else window.open(mediaUrl(res.url), "_blank");
    } catch (err) {
      tab?.close();
      setError(errorMessage(err));
    }
  };

  // Khung xương 3D HLV - HV hiện ngay dưới bình luận điểm (bấm lần nữa để ẩn)
  const toggleSkeleton3D = async () => {
    if (skeletonUrl) {
      setSkeletonUrl(null);
      return;
    }
    try {
      const res = await call<{ skeleton_url?: string | null }>("get_grading_result", { id: post.id });
      if (!res.skeleton_url) throw new Error("no-skeleton");
      setSkeletonUrl(res.skeleton_url);
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  const handleDelete = async () => {
    setMenuOpen(false);
    if (!confirm("Xóa bài viết này? Thao tác không thể hoàn tác.")) return;
    try {
      await call("delete_post", { id: post.id });
      onRemoved?.(post.id);
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  const handleBlock = async () => {
    setMenuOpen(false);
    if (!confirm(`Chặn ${post.author?.username}? Hai người sẽ không xem được trang và không nhắn tin được với nhau.`)) return;
    try {
      await call("set_block", { user_id: post.user_id, type: 0 });
      onRemoved?.(post.id);
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  const handleReport = async () => {
    try {
      await call("report_post", { id: post.id, subject: reportSubject, details: reportDetails });
      setModal(null);
      setReportDetails("");
      alert("Đã gửi báo cáo. Cảm ơn bạn!");
    } catch (err) {
      setModal(null);
      setError(errorMessage(err));
    }
  };

  const formatDate = (dateStr: string) => {
    try {
      const d = new Date(dateStr);
      return d.toLocaleDateString("vi-VN", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return dateStr;
    }
  };

  const isOwner = tokenData?.user_id === post.user_id;
  const content = emojify(post.content || "");
  const isLong = content.length > PREVIEW_CHARS;

  return (
    <div className="bg-slate-900/90 rounded-2xl border border-slate-800 p-5 shadow-lg text-white">
      {/* Header bài đăng */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <Link href={`/profile/${post.user_id}`} className="w-10 h-10 rounded-full bg-gradient-to-tr from-blue-600 to-indigo-600 flex items-center justify-center font-bold text-sm">
            {post.author?.username?.[0]?.toUpperCase() || <UserIcon className="w-5 h-5" />}
          </Link>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <Link href={`/profile/${post.user_id}`} className="font-semibold text-sm hover:underline">{post.author?.username || `User #${post.user_id}`}</Link>
              <span className="text-[10px] bg-slate-800 text-slate-400 px-2 py-0.5 rounded-full border border-slate-700 uppercase font-semibold">
                {post.author?.role || "student"}
              </span>
              {post.is_exercise && (
                <span className="text-[10px] bg-amber-500/20 text-amber-300 px-2 py-0.5 rounded-full border border-amber-500/30 font-semibold">
                  Bài tập · {post.submissions_count ?? 0} bài nộp
                </span>
              )}
              {post.lecturer && (
                <span className="text-[11px] text-slate-400">nộp bài của <span className="font-semibold text-slate-300">{post.lecturer.username}</span></span>
              )}
            </div>
            <p className="text-[11px] text-slate-500">
              <Link href={`/posts/${post.id}`} className="hover:underline">{formatDate(post.created_at)}</Link>
              {(post.edited_times ?? 0) > 0 && " · Đã chỉnh sửa"}
            </p>
          </div>
        </div>

        {isAuthenticated && (
          <div className="relative">
            <button onClick={() => setMenuOpen(!menuOpen)} className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition" aria-label="Tùy chọn">
              <MoreHorizontal className="w-4 h-4" />
            </button>
            {menuOpen && (
              <div className="absolute right-0 z-20 mt-1 w-52 rounded-xl border border-slate-700 bg-slate-900 p-1 text-xs shadow-2xl" onMouseLeave={() => setMenuOpen(false)}>
                {post.can_edit && (
                  <button onClick={() => { setMenuOpen(false); setModal("edit"); }} className="flex w-full items-center gap-2 rounded-lg px-3 py-2 hover:bg-slate-800"><Pencil className="w-3.5 h-3.5" /> Chỉnh sửa bài viết</button>
                )}
                {post.can_delete && (
                  <button onClick={handleDelete} className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-rose-400 hover:bg-slate-800"><Trash2 className="w-3.5 h-3.5" /> Xóa bài viết</button>
                )}
                {!isOwner && (
                  <button onClick={() => { setMenuOpen(false); setModal("report"); }} className="flex w-full items-center gap-2 rounded-lg px-3 py-2 hover:bg-slate-800"><Flag className="w-3.5 h-3.5" /> Báo cáo bài viết</button>
                )}
                {!isOwner && (
                  <button onClick={handleBlock} className="flex w-full items-center gap-2 rounded-lg px-3 py-2 hover:bg-slate-800"><Ban className="w-3.5 h-3.5" /> Chặn {post.author?.username}</button>
                )}
                {isOwner && !post.can_edit && !post.can_delete && <p className="px-3 py-2 text-slate-500">Bài tập đã có học viên nộp nên không thể sửa / xóa.</p>}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Nội dung bài đăng (kèm hashtag) - "Xem thêm" mở rộng, không thu gọn lại (Slide 30) */}
      <p className="text-sm text-slate-200 leading-relaxed mb-4 whitespace-pre-line break-words">
        {isLong && !expanded ? content.slice(0, PREVIEW_CHARS) + "…" : content}
        {isLong && !expanded && (
          <button onClick={() => setExpanded(true)} className="ml-1 text-xs font-semibold text-blue-400 hover:underline">Xem thêm</button>
        )}
      </p>

      {/* Video đính kèm (góc trái / phải, video ghép nếu có) */}
      {(post.video_left_url || post.video_right_url) && (
        <div className="mb-4 space-y-2 bg-slate-950 p-2 rounded-xl border border-slate-800">
          {post.video_fused_url && (
            <div className="bg-slate-900 rounded-lg p-2 border border-slate-800">
              <p className="text-[11px] font-semibold text-slate-300 mb-1 flex items-center gap-1"><Video className="w-3.5 h-3.5 text-emerald-400" /> Video ghép 2 góc quay</p>
              <video src={mediaUrl(post.video_fused_url)} controls preload="metadata" className="w-full rounded-md bg-black" />
            </div>
          )}
          <div className={`grid gap-2 ${post.video_left_url && post.video_right_url ? "grid-cols-2" : "grid-cols-1"}`}>
            {post.video_left_url && (
              <div className="bg-slate-900 rounded-lg p-2 text-center border border-slate-800">
                <p className="text-[11px] font-semibold text-slate-300 mb-1 flex items-center justify-center gap-1"><Video className="w-3.5 h-3.5 text-blue-400" /> Góc Quay Trái</p>
                <video src={mediaUrl(post.video_left_url)} poster={post.thumbnail_url ? mediaUrl(post.thumbnail_url) : undefined} controls preload="metadata" className="w-full rounded-md bg-black" />
              </div>
            )}
            {post.video_right_url && (
              <div className="bg-slate-900 rounded-lg p-2 text-center border border-slate-800">
                <p className="text-[11px] font-semibold text-slate-300 mb-1 flex items-center justify-center gap-1"><Video className="w-3.5 h-3.5 text-indigo-400" /> Góc Quay Phải</p>
                <video src={mediaUrl(post.video_right_url)} controls preload="metadata" className="w-full rounded-md bg-black" />
              </div>
            )}
          </div>
        </div>
      )}

      {/* Đính kèm bài nộp điểm số nếu có */}
      {post.submission && (
        <div className="mb-4 bg-slate-950/70 rounded-xl border border-slate-800 p-3.5 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 flex items-center justify-center">
              <Award className="w-5 h-5" />
            </div>
            <div>
              <p className="text-xs font-semibold text-slate-200">
                Kết quả bài nộp: {post.submission.score !== null && post.submission.score !== undefined ? `${post.submission.score}/100 điểm` : "Đang xử lý"}
              </p>
              <p className="text-[11px] text-slate-400 line-clamp-1">
                {post.submission.feedback_text || "Được đánh giá bằng mô hình DTW & Pose 3D"}
              </p>
            </div>
          </div>
          <Link
            href={`/submissions/${post.submission.id}`}
            className="flex items-center gap-1.5 bg-blue-600/20 hover:bg-blue-600 text-blue-400 hover:text-white border border-blue-500/30 text-xs px-3 py-1.5 rounded-lg transition"
          >
            <Play className="w-3.5 h-3.5" />
            Xem Chi Tiết
          </Link>
        </div>
      )}

      {/* Tương tác: Thích, Bình luận, Nộp bài / Chia sẻ */}
      <div className="pt-3 border-t border-slate-800/80 flex items-center gap-6 text-xs text-slate-400 mb-3">
        <button
          onClick={handleLike}
          className={`flex items-center gap-1.5 transition ${isLiked ? "text-rose-500 font-semibold" : "hover:text-rose-400"}`}
        >
          <Heart className={`w-4 h-4 ${isLiked ? "fill-rose-500 animate-like-pop" : ""}`} />
          <span>{likesCount} Yêu thích</span>
        </button>

        <button
          onClick={() => setShowComments(!showComments)}
          className="flex items-center gap-1.5 hover:text-blue-400 transition"
        >
          <MessageSquare className="w-4 h-4" />
          <span>{comments.length} Bình luận</span>
        </button>

        {post.can_submit ? (
          <button
            onClick={() => requireLogin() && setModal("submit")}
            className="flex items-center gap-1.5 ml-auto bg-emerald-600/20 hover:bg-emerald-600 text-emerald-400 hover:text-white border border-emerald-500/30 px-3 py-1.5 rounded-lg font-semibold transition"
          >
            <UploadCloud className="w-4 h-4" />
            <span>Nộp bài</span>
          </button>
        ) : (
          <button
            onClick={() => navigator.clipboard?.writeText(`${window.location.origin}/posts/${post.id}`)}
            className="flex items-center gap-1.5 hover:text-slate-200 transition ml-auto"
            title="Sao chép liên kết bài viết"
          >
            <Share2 className="w-4 h-4" />
            <span>Chia sẻ</span>
          </button>
        )}
      </div>

      {error && (
        <div className="mb-3 p-2.5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs">{error}</div>
      )}

      {/* Khu vực Bình luận (Bao gồm comment của AI Auto-Bot - Slide 8 & 42) */}
      {showComments && (
        <div className="mt-3 pt-3 border-t border-slate-800/60 space-y-2.5">
          {comments.map((cmt) => (
            <div
              key={cmt.id}
              className={`p-3 rounded-xl text-xs ${
                cmt.is_bot_evaluation
                  ? "bg-blue-950/40 border border-blue-500/30 text-blue-200"
                  : "bg-slate-950/60 border border-slate-800/80 text-slate-300"
              }`}
            >
              <div className="flex items-center gap-2 mb-1">
                {cmt.is_bot_evaluation ? (
                  <span className="inline-flex items-center gap-1 text-[10px] bg-blue-500/20 text-blue-400 font-bold px-2 py-0.5 rounded-full border border-blue-400/30">
                    <Bot className="w-3 h-3" />
                    AI Auto-Scorer
                  </span>
                ) : (
                  <span className="font-semibold text-slate-200">
                    {cmt.user?.username || `User #${cmt.user_id}`}
                  </span>
                )}
                <span className="text-[10px] text-slate-500">{formatDate(cmt.created_at)}</span>
              </div>
              <p className="whitespace-pre-line leading-relaxed break-words">{emojify(cmt.content)}</p>
              {cmt.detail_mistakes && (
                <button
                  onClick={() => setDetailHtml(cmt.detail_mistakes || null)}
                  className="mt-2 inline-flex items-center gap-1.5 bg-blue-600/20 hover:bg-blue-600 text-blue-300 hover:text-white border border-blue-500/30 px-2.5 py-1 rounded-lg font-semibold transition"
                >
                  <FileText className="w-3.5 h-3.5" /> Xem chi tiết lỗi
                </button>
              )}
              {cmt.is_bot_evaluation && cmt.score != null && (
                <>
                  <button
                    onClick={toggleSkeleton3D}
                    className="mt-2 ml-2 inline-flex items-center gap-1.5 bg-blue-600/20 hover:bg-blue-600 text-blue-300 hover:text-white border border-blue-500/30 px-2.5 py-1 rounded-lg font-semibold transition"
                  >
                    <Axis3d className="w-3.5 h-3.5" /> {skeletonUrl ? "Ẩn 3D" : "Xem 3D"}
                  </button>
                  <button
                    onClick={downloadResultZip}
                    className="mt-2 ml-2 inline-flex items-center gap-1.5 bg-blue-600/20 hover:bg-blue-600 text-blue-300 hover:text-white border border-blue-500/30 px-2.5 py-1 rounded-lg font-semibold transition"
                  >
                    <Download className="w-3.5 h-3.5" /> Tải kết quả (.zip)
                  </button>
                  {skeletonUrl && <div className="mt-3"><Skeleton3DViewer url={skeletonUrl} /></div>}
                </>
              )}
            </div>
          ))}

          {/* Ô nhập bình luận */}
          {isAuthenticated && (
            <form onSubmit={handleSendComment} className="flex gap-2 mt-2">
              <input
                type="text"
                value={newComment}
                onChange={(e) => setNewComment(e.target.value)}
                placeholder="Viết bình luận hoặc trao đổi kỹ thuật... (gõ :) để chèn emoticon)"
                className="flex-1 bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
              />
              <button
                type="submit"
                disabled={isSendingComment || !newComment.trim()}
                className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white px-3.5 py-2 rounded-xl transition flex items-center justify-center shadow-md shadow-blue-500/20"
              >
                <Send className="w-3.5 h-3.5" />
              </button>
            </form>
          )}
        </div>
      )}

      {/* Nộp bài (HV) / Sửa bài (video_indices) */}
      <VideoPostModal open={modal === "submit"} mode="submit" post={post as any} onClose={() => setModal(null)}
        onDone={(id) => router.push(`/posts/${id}`)} />
      <VideoPostModal open={modal === "edit"} mode="edit" post={post as any} onClose={() => setModal(null)} onDone={reload} />

      <Modal open={modal === "report"} onClose={() => setModal(null)} title="Báo cáo bài viết">
        <div className="space-y-2 text-sm">
          {REPORT_SUBJECTS.map((s) => (
            <label key={s} className="flex items-center gap-2"><input type="radio" checked={reportSubject === s} onChange={() => setReportSubject(s)} /> {s}</label>
          ))}
          <textarea className="input" rows={3} placeholder="Chi tiết (không bắt buộc)" value={reportDetails} onChange={(e) => setReportDetails(e.target.value)} />
          <button onClick={handleReport} className="btn-primary w-full">Gửi báo cáo</button>
        </div>
      </Modal>

      <Modal open={!!detailHtml} onClose={() => setDetailHtml(null)} title="Chi tiết lỗi động tác" wide>
        <ReportFrame html={detailHtml} />
        {post.submission_id && (
          <Link href={`/submissions/${post.submission_id}`} className="btn-primary mt-3 w-full">Xem video đối sánh HLV - HV</Link>
        )}
      </Modal>
    </div>
  );
};
