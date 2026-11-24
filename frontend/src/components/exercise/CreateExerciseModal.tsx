"use client";

import React, { useState, useRef } from "react";
import { X, Video, Plus, AlertCircle, CheckCircle2, Loader2, Dumbbell } from "lucide-react";
import { exerciseService } from "../../services/apiClient";

interface CreateExerciseModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export const CreateExerciseModal: React.FC<CreateExerciseModalProps> = ({ isOpen, onClose, onSuccess }) => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [title, setTitle] = useState("");
  const [category, setCategory] = useState("military");
  const [description, setDescription] = useState("");
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!videoFile) {
      setErrorMessage("Vui lòng tải lên video bài mẫu chuẩn của HLV.");
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      const formData = new FormData();
      formData.append("title", title);
      formData.append("category", category);
      formData.append("description", description);
      formData.append("file", videoFile);

      await exerciseService.createExercise(formData);
      onSuccess();
      onClose();
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      setErrorMessage(typeof detail === "object" ? detail.message : detail || "Đăng bài tập thất bại.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-fade-in text-white">
      <div className="bg-slate-900 border border-slate-800 rounded-3xl max-w-lg w-full p-6 shadow-2xl relative">
        <button
          onClick={onClose}
          className="absolute top-5 right-5 text-slate-400 hover:text-white p-1 hover:bg-slate-800 rounded-full transition"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="flex items-center gap-3 mb-5">
          <div className="p-3 bg-blue-500/10 rounded-2xl text-blue-400">
            <Dumbbell className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-lg font-bold">Thêm Bài Tập Mẫu Chuẩn (HLV)</h2>
            <p className="text-xs text-slate-400">Tải lên video hướng dẫn mẫu để học viên luyện tập và đối sánh</p>
          </div>
        </div>

        {errorMessage && (
          <div className="mb-4 flex items-center gap-2 p-3 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-xs">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{errorMessage}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1">Tên bài tập động tác *</label>
            <input
              type="text"
              required
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Ví dụ: Động tác Quay Phải Chuẩn"
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-white focus:outline-none focus:border-blue-500"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1">Chủ đề huấn luyện *</label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-white focus:outline-none focus:border-blue-500"
            >
              <option value="military">Điều lệnh Quân sự</option>
              <option value="sword_dance">Múa kiếm cổ phong</option>
              <option value="artistic_dance">Vũ đạo nghệ thuật</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1">Mô tả và lưu ý kỹ thuật</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Mô tả các góc độ khuỷu tay, tư thế chân và biên độ cần đạt..."
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-white focus:outline-none focus:border-blue-500 resize-none h-20"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1">Video bài mẫu chuẩn của HLV *</label>
            <div
              onClick={() => fileInputRef.current?.click()}
              className={`border-2 border-dashed rounded-2xl p-4 text-center cursor-pointer transition flex flex-col items-center justify-center min-h-[110px] ${
                videoFile ? "border-emerald-500 bg-emerald-500/10" : "border-slate-700 hover:border-blue-500 bg-slate-950"
              }`}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept="video/*"
                onChange={(e) => setVideoFile(e.target.files?.[0] || null)}
                className="hidden"
              />
              <Video className={`w-6 h-6 mb-1.5 ${videoFile ? "text-emerald-400" : "text-slate-400"}`} />
              <span className="text-xs font-semibold text-white">
                {videoFile ? videoFile.name : "Nhấp để chọn file video mẫu (MP4, AVI, MOV)"}
              </span>
              <span className="text-[10px] text-slate-500 mt-1">Dung lượng tối đa 100MB</span>
            </div>
          </div>

          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={isSubmitting}
              className="flex-1 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold py-2.5 rounded-xl transition"
            >
              Hủy
            </button>
            <button
              type="submit"
              disabled={isSubmitting || !title || !videoFile}
              className="flex-1 flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-xs font-semibold py-2.5 rounded-xl transition shadow-md shadow-blue-500/20"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Đang tải lên...
                </>
              ) : (
                "Đăng Bài Mẫu"
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
