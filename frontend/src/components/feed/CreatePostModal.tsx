"use client";

import React, { useState } from "react";
import { X, Send, Sparkles, Loader2 } from "lucide-react";
import { postService } from "../../services/apiClient";
import { Post } from "../../types/post";

interface CreatePostModalProps {
  isOpen: boolean;
  onClose: () => void;
  onPostCreated: (post: Post) => void;
  defaultSubmissionId?: number;
}

export const CreatePostModal: React.FC<CreatePostModalProps> = ({
  isOpen,
  onClose,
  onPostCreated,
  defaultSubmissionId,
}) => {
  const [content, setContent] = useState<string>("");
  const [submissionId, setSubmissionId] = useState<number | undefined>(defaultSubmissionId);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!content.trim()) return;

    setIsSubmitting(true);
    setError(null);

    try {
      const created = await postService.createPost({
        content: content.trim(),
        submission_id: submissionId,
      });
      onPostCreated(created);
      setContent("");
      onClose();
    } catch (err: any) {
      setError(err.response?.data?.detail || "Không thể đăng bài. Vui lòng thử lại sau.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-slate-900 border border-slate-800 rounded-3xl max-w-lg w-full p-6 text-white shadow-2xl relative">
        <button
          onClick={onClose}
          className="absolute top-5 right-5 p-2 rounded-xl bg-slate-800/80 text-slate-400 hover:text-white transition"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-xl bg-blue-600/20 text-blue-400 border border-blue-500/30 flex items-center justify-center">
            <Sparkles className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-lg font-bold">Chia Sẻ Với Cộng Đồng</h3>
            <p className="text-xs text-slate-400">Chia sẻ kinh nghiệm luyện tập, động tác hay thành tích</p>
          </div>
        </div>

        {error && (
          <div className="mb-4 p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            rows={4}
            placeholder="Hôm nay bạn đã luyện tập bài gì? Cảm nhận về góc khớp và nhịp động tác ra sao?..."
            className="w-full bg-slate-950/70 border border-slate-700/80 rounded-2xl p-4 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 transition resize-none"
            required
          />

          {submissionId && (
            <div className="mt-3 p-2.5 rounded-xl bg-blue-500/10 border border-blue-500/20 text-xs text-blue-300 flex items-center justify-between">
              <span>Đính kèm kết quả bài nộp #{submissionId}</span>
              <button
                type="button"
                onClick={() => setSubmissionId(undefined)}
                className="text-slate-400 hover:text-white"
              >
                Gỡ
              </button>
            </div>
          )}

          <div className="mt-5 flex items-center justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-xs font-semibold text-slate-400 hover:text-white transition"
            >
              Hủy
            </button>
            <button
              type="submit"
              disabled={isSubmitting || !content.trim()}
              className="flex items-center gap-2 px-6 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-xs font-semibold transition shadow-lg shadow-blue-500/25"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Đang đăng...
                </>
              ) : (
                <>
                  <Send className="w-4 h-4" />
                  Đăng Bài
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
