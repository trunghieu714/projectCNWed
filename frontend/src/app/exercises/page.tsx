"use client";

import React, { useState, useEffect } from "react";
import { Dumbbell, Search, Filter, Plus, Shield, Flame, Sparkles, Award } from "lucide-react";
import { Exercise } from "../../types/exercise";
import { exerciseService } from "../../services/apiClient";
import { ExerciseCard } from "../../components/exercise/ExerciseCard";
import { VideoUploadModal } from "../../components/exercise/VideoUploadModal";
import { CreateExerciseModal } from "../../components/exercise/CreateExerciseModal";
import { useAuth } from "../../hooks/useAuth";

export default function ExercisesPage() {
  const { isCoach } = useAuth();
  const [exercises, setExercises] = useState<Exercise[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [selectedExercise, setSelectedExercise] = useState<Exercise | null>(null);
  const [isUploadModalOpen, setIsUploadModalOpen] = useState<boolean>(false);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const categories = [
    { id: "all", label: "Tất cả", icon: Dumbbell },
    { id: "military", label: "Điều lệnh Quân sự", icon: Shield },
    { id: "sword_dance", label: "Múa kiếm", icon: Flame },
    { id: "artistic_dance", label: "Vũ đạo nghệ thuật", icon: Sparkles },
  ];

  const fetchExercises = () => {
    setIsLoading(true);
    exerciseService
      .getExercises(selectedCategory === "all" ? undefined : selectedCategory)
      .then((data) => {
        setExercises(data);
        setIsLoading(false);
      })
      .catch(() => {
        setExercises([]);
        setIsLoading(false);
      });
  };

  useEffect(() => {
    fetchExercises();
  }, [selectedCategory]);

  const filteredExercises = exercises.filter((ex) =>
    ex.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
    (ex.description && ex.description.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-8">
      {/* Header Phân Biệt Quyền Rõ Ràng */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <span
              className={`text-xs font-bold px-3 py-1 rounded-full border uppercase tracking-wider ${
                isCoach
                  ? "bg-amber-500/15 border-amber-500/30 text-amber-300"
                  : "bg-emerald-500/15 border-emerald-500/30 text-emerald-300"
              }`}
            >
              {isCoach ? "🎖️ Quản Trị Huấn Luyện Viên" : "🎓 Không Gian Luyện Tập Học Viên"}
            </span>
          </div>
          <h1 className="text-3xl font-black text-white">
            {isCoach ? "Quản Lý Kho Bài Tập Mẫu" : "Kho Bài Tập Vận Động"}
          </h1>
          <p className="text-sm text-slate-400 mt-1 max-w-2xl leading-relaxed">
            {isCoach
              ? "Bạn có thể tải lên các bài tập mẫu mới kèm video chuẩn để trích xuất Pose 3D và làm căn cứ đối sánh cho học viên."
              : "Chọn bài tập mẫu chuẩn của Huấn luyện viên, xem kỹ hướng dẫn và nộp video thực hiện để nhận đánh giá chi tiết."}
          </p>
        </div>

        {/* Nút Tạo Bài Tập Dành Riêng Cho Huấn Luyện Viên */}
        {isCoach && (
          <button
            onClick={() => setIsCreateModalOpen(true)}
            className="flex items-center justify-center gap-2 bg-gradient-to-r from-amber-600 to-orange-600 hover:from-amber-500 hover:to-orange-500 text-white font-bold px-5 py-3 rounded-2xl shadow-xl shadow-amber-500/20 transition active:scale-95 text-xs sm:text-sm border border-amber-400/30 shrink-0"
          >
            <Plus className="w-4 h-4" />
            + Đăng Bài Tập Mới (HLV)
          </button>
        )}
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col md:flex-row items-center justify-between gap-4">
        {/* Category Tabs */}
        <div className="flex flex-wrap items-center gap-2 bg-slate-900 p-1.5 rounded-2xl border border-slate-800 w-full md:w-auto">
          {categories.map((cat) => {
            const Icon = cat.icon;
            const isSelected = selectedCategory === cat.id;
            return (
              <button
                key={cat.id}
                onClick={() => setSelectedCategory(cat.id)}
                className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition ${
                  isSelected
                    ? isCoach
                      ? "bg-amber-600 text-white shadow-md shadow-amber-500/20"
                      : "bg-blue-600 text-white shadow-md shadow-blue-500/20"
                    : "text-slate-400 hover:text-white hover:bg-slate-800"
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                {cat.label}
              </button>
            );
          })}
        </div>

        {/* Search Input */}
        <div className="relative w-full md:w-72">
          <Search className="w-4 h-4 text-slate-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Tìm kiếm bài tập..."
            className="w-full bg-slate-900 border border-slate-800 rounded-xl pl-10 pr-4 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 transition"
          />
        </div>
      </div>

      {/* Exercises Grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {[1, 2, 3].map((n) => (
            <div key={n} className="bg-slate-900/60 rounded-2xl border border-slate-800 p-6 h-60 animate-pulse" />
          ))}
        </div>
      ) : filteredExercises.length === 0 ? (
        <div className="bg-slate-900/40 rounded-2xl border border-slate-800/80 p-12 text-center text-slate-400">
          <Dumbbell className="w-12 h-12 mx-auto mb-3 opacity-30" />
          <p className="text-sm font-semibold text-slate-300">Không tìm thấy bài tập nào phù hợp</p>
          <p className="text-xs text-slate-500 mt-1">Hãy thử tìm kiếm với từ khóa khác hoặc chuyển danh mục.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {filteredExercises.map((ex) => (
            <ExerciseCard
              key={ex.id}
              exercise={ex}
              onOpenUpload={(item) => {
                setSelectedExercise(item);
                setIsUploadModalOpen(true);
              }}
            />
          ))}
        </div>
      )}

      {/* Modal Nộp Bài Tập Dành Cho Học Viên */}
      {selectedExercise && (
        <VideoUploadModal
          exercise={selectedExercise}
          isOpen={isUploadModalOpen}
          onClose={() => setIsUploadModalOpen(false)}
        />
      )}

      {/* Modal Đăng Bài Mẫu Mới Dành Cho Huấn Luyện Viên */}
      {isCoach && (
        <CreateExerciseModal
          isOpen={isCreateModalOpen}
          onClose={() => setIsCreateModalOpen(false)}
          onSuccess={() => {
            setIsCreateModalOpen(false);
            fetchExercises();
          }}
        />
      )}
    </div>
  );
}