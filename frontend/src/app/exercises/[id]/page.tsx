"use client";

import React, { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Play, UploadCloud, Shield, CheckCircle2, User, Clock, AlertCircle, Award, Users, ChevronRight, Activity } from "lucide-react";
import { Exercise } from "../../../types/exercise";
import { SubmissionResponse } from "../../../types/submission";
import { exerciseService, submissionService } from "../../../services/apiClient";
import { VideoUploadModal } from "../../../components/exercise/VideoUploadModal";
import { useAuth } from "../../../hooks/useAuth";
import { getVideoUrl } from "../../../utils/media";

export default function ExerciseDetailPage() {
  const params = useParams();
  const router = useRouter();
  const exerciseId = Number(params?.id);
  const { user, isCoach } = useAuth();

  const [exercise, setExercise] = useState<Exercise | null>(null);
  const [submissions, setSubmissions] = useState<SubmissionResponse[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isUploadOpen, setIsUploadOpen] = useState<boolean>(false);

  useEffect(() => {
    if (!exerciseId) return;
    setIsLoading(true);

    // 1. Lấy thông tin bài tập
    exerciseService
      .getExerciseById(exerciseId)
      .then((data) => {
        setExercise(data);
      })
      .catch(() => {
        setExercise(null);
      })
      .finally(() => setIsLoading(false));

    // 2. Tải danh sách bài nộp theo vai trò
    if (isCoach) {
      submissionService
        .getExerciseSubmissions(exerciseId)
        .then((subs) => setSubmissions(subs))
        .catch(() => setSubmissions([]));
    } else {
      submissionService
        .getMyHistory()
        .then((subs) => setSubmissions(subs.filter((s) => s.exercise_id === exerciseId)))
        .catch(() => setSubmissions([]));
    }
  }, [exerciseId, isCoach]);

  if (isLoading) {
    return (
      <div className="max-w-5xl mx-auto px-4 py-16 text-center text-slate-400">
        Đang tải thông tin bài tập...
      </div>
    );
  }

  if (!exercise) {
    return (
      <div className="max-w-5xl mx-auto px-4 py-16 text-center text-slate-400">
        Không tìm thấy bài tập yêu cầu.
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-8">
      {/* Nút Quay lại */}
      <Link
        href="/exercises"
        className="inline-flex items-center gap-2 text-xs font-semibold text-slate-400 hover:text-white transition"
      >
        <ArrowLeft className="w-4 h-4" />
        Quay lại Danh sách Bài tập
      </Link>

      {/* Header Bài tập - Phân biệt quyền rõ ràng */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span
              className={`text-[11px] px-3 py-0.5 rounded-full font-bold uppercase tracking-wider border ${
                isCoach
                  ? "bg-amber-500/20 text-amber-300 border-amber-500/30"
                  : "bg-emerald-500/20 text-emerald-300 border-emerald-500/30"
              }`}
            >
              {isCoach ? "🎖️ Bài Mẫu Huấn Luyện Viên" : "🎓 Bài Tập Luyện Tập"}
            </span>
            <span className="bg-blue-500/20 text-blue-400 border border-blue-500/30 text-xs px-2.5 py-0.5 rounded-full font-semibold uppercase">
              {exercise.category}
            </span>
          </div>
          <h1 className="text-3xl font-black text-white">{exercise.title}</h1>
        </div>

        {/* Action Button Phân Biệt Theo Quyền */}
        {isCoach ? (
          <div className="flex items-center gap-2 bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs font-semibold px-4 py-2.5 rounded-xl">
            <span>🛡️ Chế độ Huấn Luyện Viên: Đang theo dõi bài nộp của học viên</span>
          </div>
        ) : (
          <button
            onClick={() => setIsUploadOpen(true)}
            className="flex items-center justify-center gap-2 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold px-6 py-3 rounded-2xl shadow-lg shadow-emerald-500/25 transition active:scale-95 text-sm"
          >
            <UploadCloud className="w-4 h-4" />
            Nộp Bài Tập Để Chấm Điểm
          </button>
        )}
      </div>

      {/* Video HLV Mẫu */}
      <div className="rounded-2xl overflow-hidden bg-black border border-slate-800 shadow-2xl relative">
        <div className="absolute top-4 left-4 z-10 bg-emerald-600/90 text-xs font-bold px-3 py-1.5 rounded-lg flex items-center gap-1.5 backdrop-blur-md">
          <Play className="w-3.5 h-3.5 fill-white" />
          Video Bài Mẫu Của Huấn Luyện Viên
        </div>
        <video
          src={getVideoUrl(exercise.coach_video_url)}
          controls
          className="w-full aspect-video object-cover"
        />
      </div>

      {/* Hướng dẫn chi tiết & Tiêu chí kỹ thuật */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="md:col-span-2 bg-slate-900/80 rounded-2xl border border-slate-800 p-6 space-y-4">
          <h3 className="text-lg font-bold text-white">Yêu Cầu & Hướng Dẫn Kỹ Thuật</h3>
          <p className="text-slate-300 text-sm leading-relaxed whitespace-pre-line">
            {exercise.description}
          </p>

          <div className="pt-4 border-t border-slate-800 space-y-2">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400">
              Các điểm trọng tâm AI sẽ đánh giá qua FastDTW:
            </h4>
            <ul className="space-y-1.5 text-xs text-slate-300">
              <li className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                Độ chuẩn xác góc khuỷu tay so với thân người (sai lệch cho phép ±15°).
              </li>
              <li className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                Độ thẳng của cột sống và cân bằng trọng tâm hai vai.
              </li>
              <li className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                Nhịp điệu dứt khoát khớp với đường cong thời gian DTW của video mẫu.
              </li>
            </ul>
          </div>
        </div>

        <div className="bg-slate-900/80 rounded-2xl border border-slate-800 p-6 space-y-4 text-xs text-slate-400">
          <h3 className="text-base font-bold text-white">Thông Tin Bài Tập</h3>
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <User className="w-4 h-4 text-blue-400" />
              <span>Người tạo: Huấn luyện viên #{exercise.created_by}</span>
            </div>
            <div className="flex items-center gap-2">
              <Clock className="w-4 h-4 text-emerald-400" />
              <span>Cập nhật: {new Date(exercise.created_at).toLocaleDateString("vi-VN")}</span>
            </div>
            <div className="flex items-center gap-2">
              <Shield className="w-4 h-4 text-purple-400" />
              <span>Chuẩn dữ liệu: GVHMR 3D Pose</span>
            </div>
          </div>
        </div>
      </div>

      {/* ================= PHẦN DÀNH CHO HUẤN LUYỆN VIÊN: DANH SÁCH BÀI NỘP CỦA HỌC VIÊN ================= */}
      {isCoach && (
        <div className="space-y-4 pt-6 border-t border-slate-800">
          <div className="flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2 text-amber-400 text-xs font-bold uppercase tracking-wider mb-1">
                <Users className="w-4 h-4" />
                <span>BẢNG QUẢN LÝ BÀI NỘP CỦA HỌC VIÊN</span>
              </div>
              <h3 className="text-xl font-bold text-white">
                Danh Sách Bài Nộp Của Học Viên ({submissions.length})
              </h3>
            </div>
          </div>

          {submissions.length === 0 ? (
            <div className="bg-slate-900/40 rounded-2xl border border-slate-800/80 p-8 text-center text-slate-400">
              <Users className="w-10 h-10 mx-auto mb-2 opacity-30 text-amber-400" />
              <p className="text-sm font-semibold text-slate-300">Chưa có bài nộp nào từ học viên cho bài tập này</p>
              <p className="text-xs text-slate-500 mt-1">Khi học viên nộp video, kết quả chấm điểm AI sẽ tự động xuất hiện tại đây.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {submissions.map((sub) => {
                const studentName = sub.student?.full_name || sub.student?.username || `Học viên #${sub.student_id}`;
                const isPassed = (sub.score || 0) >= 70;
                return (
                  <div
                    key={sub.id}
                    className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 rounded-2xl bg-slate-900/90 border border-slate-800 hover:border-slate-700 transition"
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center font-bold text-slate-200">
                        {studentName.charAt(0).toUpperCase()}
                      </div>
                      <div>
                        <div className="font-bold text-white text-sm flex items-center gap-2">
                          <span>{studentName}</span>
                          <span className="text-[11px] text-slate-400 font-normal">
                            (Nộp: {new Date(sub.created_at).toLocaleString("vi-VN")})
                          </span>
                        </div>
                        <p className="text-xs text-slate-400 line-clamp-1 mt-0.5">
                          {sub.feedback_text || "Đang được hệ thống phân tích..."}
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-4">
                      {sub.score !== undefined && sub.score !== null ? (
                        <div className="text-right">
                          <span
                            className={`inline-block px-3 py-1 rounded-full text-xs font-black ${
                              isPassed
                                ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                                : "bg-amber-500/20 text-amber-300 border border-amber-500/30"
                            }`}
                          >
                            {sub.score} / 100 ĐIỂM
                          </span>
                        </div>
                      ) : (
                        <span className="text-xs text-slate-400 bg-slate-800 px-2.5 py-1 rounded-md">
                          {sub.status}
                        </span>
                      )}

                      <Link
                        href={`/submissions/${sub.id}`}
                        className="flex items-center gap-1.5 bg-blue-600/20 hover:bg-blue-600 border border-blue-500/30 text-blue-300 hover:text-white text-xs font-semibold py-2 px-3.5 rounded-xl transition"
                      >
                        <span>Xem Chi Tiết AI</span>
                        <ChevronRight className="w-3.5 h-3.5" />
                      </Link>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* ================= PHẦN DÀNH CHO HỌC VIÊN: LỊCH SỬ NỘP BÀI CỦA BẠN ================= */}
      {!isCoach && (
        <div className="space-y-4 pt-6 border-t border-slate-800">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-bold text-white flex items-center gap-2">
              <Activity className="w-4 h-4 text-emerald-400" />
              Lịch Sử Nộp Bài Của Bạn ({submissions.length})
            </h3>
          </div>

          {submissions.length === 0 ? (
            <div className="bg-slate-900/40 rounded-2xl border border-slate-800/80 p-6 text-center text-slate-400">
              <p className="text-xs text-slate-400">Bạn chưa nộp bài lần nào cho bài tập này. Hãy nhấn nút &quot;Nộp Bài Tập Để Chấm Điểm&quot; ở trên!</p>
            </div>
          ) : (
            <div className="space-y-3">
              {submissions.map((sub, idx) => (
                <div
                  key={sub.id}
                  className="flex items-center justify-between p-4 rounded-2xl bg-slate-900/90 border border-slate-800"
                >
                  <div>
                    <span className="text-xs font-bold text-slate-200">Lần nộp #{submissions.length - idx}</span>
                    <span className="text-xs text-slate-400 ml-2">
                      ({new Date(sub.created_at).toLocaleString("vi-VN")})
                    </span>
                    <p className="text-xs text-slate-400 mt-1">{sub.feedback_text}</p>
                  </div>

                  <div className="flex items-center gap-3">
                    {sub.score !== undefined && sub.score !== null && (
                      <span className="font-bold text-sm text-emerald-400 bg-emerald-500/10 border border-emerald-500/30 px-3 py-1 rounded-xl">
                        {sub.score} điểm
                      </span>
                    )}
                    <Link
                      href={`/submissions/${sub.id}`}
                      className="text-xs text-blue-400 hover:text-blue-300 font-semibold"
                    >
                      Xem video & đối sánh &rarr;
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Modal Nộp Bài Tập */}
      <VideoUploadModal
        exercise={exercise}
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
      />
    </div>
  );
}