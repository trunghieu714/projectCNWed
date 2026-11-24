"use client";

import React, { useState, useEffect } from "react";
import { Users, Plus, Sparkles, MessageCircle, TrendingUp } from "lucide-react";
import { Post } from "../../types/post";
import { postService } from "../../services/apiClient";
import { PostCard } from "../../components/feed/PostCard";
import { CreatePostModal } from "../../components/feed/CreatePostModal";
import { useAuth } from "../../hooks/useAuth";

export default function FeedPage() {
  const { isAuthenticated } = useAuth();
  const [posts, setPosts] = useState<Post[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);

  useEffect(() => {
    setIsLoading(true);
    postService
      .getFeed()
      .then((data) => {
        setPosts(data);
        setIsLoading(false);
      })
      .catch(() => {
        setPosts([]);
        setIsLoading(false);
      });
  }, []);

  const handlePostCreated = (newPost: Post) => {
    setPosts([newPost, ...posts]);
  };

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h1 className="text-3xl font-black text-white">Mạng Xã Hội Luyện Tập</h1>
            <span className="bg-purple-500/20 text-purple-300 border border-purple-500/30 text-xs px-2.5 py-0.5 rounded-full font-bold">
              Community
            </span>
          </div>
          <p className="text-sm text-slate-400">
            Nơi học viên và huấn luyện viên giao lưu, chia sẻ bài nộp, kinh nghiệm nắn chỉnh góc khớp
          </p>
        </div>

        <button
          onClick={() => setIsModalOpen(true)}
          className="flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-500 text-white font-semibold px-5 py-2.5 rounded-2xl shadow-lg shadow-blue-500/20 transition active:scale-95 text-xs"
        >
          <Plus className="w-4 h-4" />
          Viết Bài Mới
        </button>
      </div>

      {/* Feed List */}
      {isLoading ? (
        <div className="space-y-4">
          {[1, 2].map((n) => (
            <div key={n} className="bg-slate-900/60 rounded-2xl border border-slate-800 p-6 h-40 animate-pulse" />
          ))}
        </div>
      ) : posts.length === 0 ? (
        <div className="bg-slate-900/40 rounded-2xl border border-slate-800/80 p-12 text-center text-slate-400">
          <MessageCircle className="w-12 h-12 mx-auto mb-3 opacity-30" />
          <p className="text-sm font-semibold text-slate-300">Chưa có bài viết nào trên bản tin</p>
          <p className="text-xs text-slate-500 mt-1">Hãy là người đầu tiên chia sẻ cảm nghĩ hoặc bài nộp của bạn!</p>
        </div>
      ) : (
        <div className="space-y-5">
          {posts.map((post) => (
            <PostCard key={post.id} post={post} />
          ))}
        </div>
      )}

      <CreatePostModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onPostCreated={handlePostCreated}
      />
    </div>
  );
}
