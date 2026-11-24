"use client";

import React, { useState, useRef } from "react";
import { X, UploadCloud, Film, AlertCircle, CheckCircle2, Loader2, Video, Hash } from "lucide-react";
import { Exercise } from "../../types/exercise";
import { postService } from "../../services/apiClient";
import { useRouter } from "next/navigation";

interface VideoUploadModalProps {
  exercise: Exercise;
  isOpen: boolean;
  onClose: () => void;
}

export const VideoUploadModal: React.FC<VideoUploadModalProps> = ({ exercise, isOpen, onClose }) => {
  const router = useRouter();
  const leftFileRef = useRef<HTMLInputElement>(null);
  const rightFileRef = useRef<HTMLInputElement>(null);

  const [leftFile, setLeftFile] = useState<File | null>(null);
  const [rightFile, setRightFile] = useState<File | null>(null);
  const [described, setDescribed] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  if (!isOpen) return null;

  const autoHashtags = exercise.course_id
    ? `#course_${exercise.course_id} #exercise_${exercise.id}`
    : `#exercise_${exercise.id}`;

  const validateFile = (file: File): string | null => {
    const allowedExts = [".mp4", ".mov", ".avi", ".webm", ".mkv"];
    const ext = file.name.substring(file.name.lastIndexOf(".")).toLowerCase();
    if (!allowedExts.includes(ext)) {
      return `Định dạng ${ext} không hợp lệ. Chỉ chấp nhận: ${allowedExts.join(", ")}`;
    }
    const maxSizeMb = 100;
    if (file.size > maxSizeMb * 1024 * 1024) {
      return `Dung lượng file vượt quá giới hạn cho phép (${maxSizeMb}MB).`;
    }
    return null;
  };

  const handleLeftChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setErrorMessage(null);
    const file = e.target.files?.[0];
    if (!file) return;
    const err = validateFile(file);
    if (err) {
      setErrorMessage(err);
      return;
    }
    setLeftFile(file);
  };

  const handleRightChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setErrorMessage(null);
    const file = e.target.files?.[0];
    if (!file) return;
    const err = validateFile(file);
    if (err) {
      setErrorMessage(err);
      return;
    }
    setRightFile(file);
  };

  const handleSubmit = async () => {
    // Slide 6: Học viên được phép nộp 1 video hoặc cả 2 video
    if (!leftFile && !rightFile) {
      setErrorMessage("Vui lòng chọn ít nhất 01 video bài tập để nộp.");
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      const formData = new FormData();
      if (leftFile) formData.append("left_video", leftFile);
      if (rightFile) formData.append("right_video", rightFile);
      formData.append("described", described || `Bài nộp thực hành: ${exercise.title}`);
      if (exercise.course_id) {
        formData.append("course_id", exercise.course_id.toString());
      }
      formData.append("exercise_id", exercise.id.toString());

      const res = await postService.addPostWithVideos(formData);
      setSuccessMessage("Đăng bài nộp thành công! Hệ thống AI đang chấm ngầm và sẽ tự động comment kết quả.");
      
      setTimeout(() => {
        onClose();
        if (res?.submission_id) {
          router.push(`/submissions/${res.submission_id}`);
        } else {
          router.push("/feed");
        }
      }, 1500);

    } catch (err: any) {
      const detail = err.response?.data?.detail;
      const msg = typeof detail === "object" ? detail.message : detail || "Nộp bài thất bại. Vui lòng thử lại.";
      setErrorMessage(msg);
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-fade-in">
      <div className="bg-slate-900 border border-slate-800 rounded-3xl max-w-xl w-full p-6 shadow-2xl relative">
        <button
          onClick={onClose}
          className="absolute top-5 right-5 text-slate-400 hover:text-white transition p-1 hover:bg-slate-800 rounded-full"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="flex items-center gap-3 mb-4">
          <div className="p-3 bg-blue-500/10 rounded-2xl text-blue-400">
            <UploadCloud className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-white">Nộp Bài Tập Điều Lệnh</h2>
            <p className="text-xs text-slate-400">{exercise.title}</p>
          </div>
        </div>

        {/* Auto Hashtags Display */}
        <div className="mb-4 flex items-center gap-2 bg-slate-800/60 px-3.5 py-2 rounded-xl border border-slate-700/50">
          <Hash className="w-4 h-4 text-blue-400 shrink-0" />
          <span className="text-xs text-blue-300 font-mono font-medium">{autoHashtags}</span>
          <span className="text-[11px] text-slate-500 ml-auto">(Hệ thống tự động gắn)</span>
        </div>

        {/* Mô tả bài viết */}
        <div className="mb-4">
          <label className="block text-xs font-semibold text-slate-300 mb-1.5">Ghi chú / Cảm nghĩ luyện tập</label>
          <textarea
            value={described}
            onChange={(e) => setDescribed(e.target.value)}
            placeholder="Chia sẻ kinh nghiệm hoặc lưu ý trong quá trình thực hiện động tác..."
            className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-white focus:outline-none focus:border-blue-500 resize-none h-18"
          />
        </div>

        {/* Khu vực chọn 2 góc quay (Left & Right) */}
        <div className="grid grid-cols-2 gap-3 mb-5">
          {/* Góc Trái */}
          <div
            onClick={() => leftFileRef.current?.click()}
            className={`border-2 border-dashed rounded-2xl p-4 text-center cursor-pointer transition flex flex-col items-center justify-center min-h-[140px] ${
              leftFile ? "border-emerald-500 bg-emerald-500/5" : "border-slate-700 hover:border-blue-500 bg-slate-950/50"
            }`}
          >
            <input ref={leftFileRef} type="file" accept="video/*" onChange={handleLeftChange} className="hidden" />
            <Video className={`w-6 h-6 mb-2 ${leftFile ? "text-emerald-400" : "text-slate-400"}`} />
            <span className="text-xs font-semibold text-white mb-1">Góc Trái (Left Cam)</span>
            <span className="text-[10px] text-slate-400 truncate max-w-[150px]">
              {leftFile ? leftFile.name : "Nhấn để chọn video"}
            </span>
          </div>

          {/* Góc Phải */}
          <div
            onClick={() => rightFileRef.current?.click()}
            className={`border-2 border-dashed rounded-2xl p-4 text-center cursor-pointer transition flex flex-col items-center justify-center min-h-[140px] ${
              rightFile ? "border-emerald-500 bg-emerald-500/5" : "border-slate-700 hover:border-blue-500 bg-slate-950/50"
            }`}
          >
            <input ref={rightFileRef} type="file" accept="video/*" onChange={handleRightChange} className="hidden" />
            <Video className={`w-6 h-6 mb-2 ${rightFile ? "text-emerald-400" : "text-slate-400"}`} />
            <span className="text-xs font-semibold text-white mb-1">Góc Phải (Tùy chọn)</span>
            <span className="text-[10px] text-slate-400 truncate max-w-[150px]">
              {rightFile ? rightFile.name : "Nhấn để chọn video"}
            </span>
          </div>
        </div>

        {/* Thông báo lỗi / thành công */}
        {errorMessage && (
          <div className="mb-4 flex items-center gap-2 p-3 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-xs">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{errorMessage}</span>
          </div>
        )}
        {successMessage && (
          <div className="mb-4 flex items-center gap-2 p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-xl text-emerald-400 text-xs">
            <CheckCircle2 className="w-4 h-4 shrink-0" />
            <span>{successMessage}</span>
          </div>
        )}

        {/* Nút Submit */}
        <div className="flex gap-3">
          <button
            onClick={onClose}
            disabled={isSubmitting}
            className="flex-1 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold py-3 rounded-xl transition"
          >
            Hủy
          </button>
          <button
            onClick={handleSubmit}
            disabled={isSubmitting || (!leftFile && !rightFile)}
            className="flex-1 flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-xs font-semibold py-3 rounded-xl transition shadow-lg shadow-blue-500/25"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Đang Tải Lên & Chấm Ngầm...
              </>
            ) : (
              "Xác Nhận Nộp Bài"
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
