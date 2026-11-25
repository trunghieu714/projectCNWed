"use client";

import React, { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Share2, Loader2, AlertCircle, RefreshCw, CheckCircle2, Axis3d } from "lucide-react";
import { SubmissionResponse } from "../../../types/submission";
import { submissionService } from "../../../services/apiClient";
import { mediaUrl } from "../../../services/api";
import { Skeleton3DViewer } from "../../../components/player/Skeleton3DViewer";
import { DualVideoPlayer } from "../../../components/player/DualVideoPlayer";
import { CreatePostModal } from "../../../components/feed/CreatePostModal";

export default function SubmissionResultPage() {
  const params = useParams();
  const router = useRouter();
  const submissionId = Number(params?.id);

  const [submission, setSubmission] = useState<SubmissionResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isShareModalOpen, setIsShareModalOpen] = useState<boolean>(false);
  const [videoTime, setVideoTime] = useState<number | undefined>(undefined);

  const fetchSubmission = async () => {
    if (!submissionId) return;
    try {
      const data = await submissionService.getSubmission(submissionId);
      setSubmission(data);
    } catch {
      setSubmission(null);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchSubmission();
  }, [submissionId]);

  // Tự động polling kiểm tra trạng thái nếu đang PENDING hoặc PROCESSING
  useEffect(() => {
    if (!submission) return;
    if (submission.status === "PENDING" || submission.status === "PROCESSING") {
      const interval = setInterval(() => {
        fetchSubmission();
      }, 3000);
      return () => clearInterval(interval);
    }
  }, [submission?.status]);

  if (isLoading) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-20 text-center text-slate-400 space-y-4">
        <Loader2 className="w-8 h-8 animate-spin mx-auto text-blue-500" />
        <p className="text-sm">Đang tải kết quả đánh giá bài nộp #{submissionId}...</p>
      </div>
    );
  }

  if (!submission) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-20 text-center text-slate-400 space-y-4">
        <AlertCircle className="w-10 h-10 mx-auto text-rose-500" />
        <p className="text-base text-slate-200">Không tìm thấy thông tin bài nộp này.</p>
        <Link href="/exercises" className="text-xs text-blue-400 underline">
          Quay lại danh sách bài tập
        </Link>
      </div>
    );
  }

  // Nếu bài nộp đang được Celery Worker xử lý
  if (submission.status === "PENDING" || submission.status === "PROCESSING") {
    return (
      <div className="max-w-xl mx-auto px-4 py-20 text-center space-y-6">
        <div className="w-16 h-16 rounded-2xl bg-blue-600/20 text-blue-400 border border-blue-500/30 flex items-center justify-center mx-auto animate-pulse">
          <Loader2 className="w-8 h-8 animate-spin" />
        </div>
        <div className="space-y-2">
          <h2 className="text-2xl font-black text-white">AI Đang Phân Tích Động Tác</h2>
          <p className="text-xs text-slate-400 max-w-md mx-auto leading-relaxed">
            Celery Worker đang gửi video lên server GPU (GVHMR) để trích xuất chuỗi Pose 3D, rồi đối sánh với video HLV
            bằng DTW trên PA-MPJPE. Trang sẽ tự động cập nhật khi có kết quả (khoảng 4 – 6 phút mỗi video với GVHMR;
            lâu hơn nếu pose của video HLV chưa được tính sẵn).
          </p>
        </div>
        <button
          onClick={fetchSubmission}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs text-slate-200 font-semibold transition"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Kiểm tra ngay
        </button>
      </div>
    );
  }

  // Nếu xử lý thất bại
  if (submission.status === "FAILED") {
    return (
      <div className="max-w-xl mx-auto px-4 py-20 text-center space-y-4">
        <div className="w-16 h-16 rounded-2xl bg-rose-600/20 text-rose-400 border border-rose-500/30 flex items-center justify-center mx-auto">
          <AlertCircle className="w-8 h-8" />
        </div>
        <h2 className="text-2xl font-black text-white">Xử Lý Thất Bại</h2>
        <p className="text-xs text-rose-300 bg-rose-500/10 border border-rose-500/20 p-3 rounded-xl">
          Lỗi: {submission.error_message || "Video không phát hiện được dáng người hoặc định dạng lỗi."}
        </p>
        <Link
          href={`/exercises/${submission.exercise_id}`}
          className="inline-block bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold px-5 py-2.5 rounded-xl transition"
        >
          Thử nộp lại video khác
        </Link>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-8">
      {/* Top Nav & Share CTA */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-slate-800">
        <Link
          href="/exercises"
          className="inline-flex items-center gap-2 text-xs font-semibold text-slate-400 hover:text-white transition"
        >
          <ArrowLeft className="w-4 h-4" />
          Quay lại Danh sách Bài tập
        </Link>

        <div className="flex flex-wrap items-center gap-3">
          {submission.report_html_url && (
            <a
              href={mediaUrl(submission.report_html_url)}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 border border-blue-500/40 bg-blue-600/20 hover:bg-blue-600 text-blue-200 hover:text-white text-xs font-semibold px-4 py-2.5 rounded-xl transition active:scale-95"
            >
              <Axis3d className="w-4 h-4" />
              Xem khung xương 3D & chi tiết lỗi
            </a>
          )}
          <button
            onClick={() => setIsShareModalOpen(true)}
            className="inline-flex items-center gap-2 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white text-xs font-semibold px-4 py-2.5 rounded-xl shadow-lg shadow-blue-500/20 transition active:scale-95"
          >
            <Share2 className="w-4 h-4" />
            Chia Sẻ Lên Mạng Xã Hội
          </button>
        </div>
      </div>

      {/* Dual Synchronized Video Player */}
      <DualVideoPlayer
        coachVideoUrl={submission.coach_video_url || "storage/coach_samples/coach_1_sample_coach.mp4"}
        studentVideoUrl={submission.student_video_url}
        fusedVideoUrl={submission.fused_video_url}
        score={submission.score}
        feedback={submission.feedback_text}
        warpingPath={submission.warping_path}
        errors={submission.errors}
        onTimeChange={setVideoTime}
      />

      {/* Khung xương 3D HLV - HV đi theo video phía trên: phát / tua video thì khung xương nhảy tới đúng thời điểm */}
      {submission.report_html_url && (
        <section className="max-w-5xl mx-auto space-y-3">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h3 className="text-lg font-bold text-white">Khung xương 3D – so sánh HLV & học viên</h3>
            <p className="text-xs text-slate-400">
              Đi theo video phía trên · kéo để xoay góc nhìn · xanh dương = HLV, xanh lá = học viên, đỏ = khớp lệch
            </p>
          </div>
          <Skeleton3DViewer url={submission.report_html_url.replace(/report\.html$/, "skeleton3d.json")} time={videoTime} />
        </section>
      )}

      <CreatePostModal
        isOpen={isShareModalOpen}
        onClose={() => setIsShareModalOpen(false)}
        defaultSubmissionId={submission.id}
        onPostCreated={() => {
          router.push("/feed");
        }}
      />
    </div>
  );
}
