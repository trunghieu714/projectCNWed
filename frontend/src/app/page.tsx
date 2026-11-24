"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { Dumbbell, Activity, ShieldCheck, Zap, Users, ArrowRight, Award, CheckCircle, Plus, GraduationCap, Video, Sparkles } from "lucide-react";
import { Exercise } from "../types/exercise";
import { exerciseService } from "../services/apiClient";
import { ExerciseCard } from "../components/exercise/ExerciseCard";
import { VideoUploadModal } from "../components/exercise/VideoUploadModal";
import { CreateExerciseModal } from "../components/exercise/CreateExerciseModal";
import { useAuth } from "../hooks/useAuth";

export default function HomePage() {
  const { user, isAuthenticated, isCoach } = useAuth();
  const [exercises, setExercises] = useState<Exercise[]>([]);
  const [selectedExercise, setSelectedExercise] = useState<Exercise | null>(null);
  const [isUploadModalOpen, setIsUploadModalOpen] = useState<boolean>(false);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState<boolean>(false);

  const loadExercises = () => {
    exerciseService
      .getExercises()
      .then((data) => setExercises(data.slice(0, 3)))
      .catch(() => {
        setExercises([]);
      });
  };

  useEffect(() => {
    loadExercises();
  }, []);

  const handleOpenUpload = (ex: Exercise) => {
    setSelectedExercise(ex);
    setIsUploadModalOpen(true);
  };

  return (
    <div className="space-y-16 pb-20">
      {/* Role-Aware Banner */}
      {isAuthenticated && isCoach ? (
        <section className="relative overflow-hidden pt-12 pb-16 px-4 sm:px-6 lg:px-8 border-b border-amber-500/20 bg-gradient-to-b from-amber-950/20 via-slate-900/60 to-slate-950">
          <div className="max-w-6xl mx-auto space-y-6">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div>
                <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-400 text-xs font-bold mb-2">
                  <span>🎖️</span>
                  <span>BẢNG ĐIỀU KHIỂN HUẤN LUYỆN VIÊN</span>
                </div>
                <h1 className="text-3xl sm:text-4xl font-black text-white">
                  Xin chào, HLV {user?.full_name || user?.username}!
                </h1>
                <p className="text-slate-400 text-xs sm:text-sm mt-1">
                  Quản lý giáo trình bài tập mẫu chuẩn, theo dõi quá trình tập luyện và chấm điểm bài nộp của học viên.
                </p>
              </div>

              <div className="flex items-center gap-3">
                <button
                  onClick={() => setIsCreateModalOpen(true)}
                  className="flex items-center gap-2 bg-gradient-to-r from-amber-600 to-orange-600 hover:from-amber-500 hover:to-orange-500 text-white font-bold px-5 py-3 rounded-2xl shadow-xl shadow-amber-500/20 transition active:scale-95 text-xs sm:text-sm"
                >
                  <Plus className="w-4 h-4" />
                  + Đăng Bài Tập Mẫu
                </button>
                <Link
                  href="/courses"
                  className="flex items-center gap-2 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 font-semibold px-4 py-3 rounded-2xl transition text-xs sm:text-sm"
                >
                  <GraduationCap className="w-4 h-4" />
                  Lớp Giảng Dạy
                </Link>
              </div>
            </div>

            {/* Coach Metrics */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-5 pt-4">
              <div className="bg-slate-900/80 border border-amber-500/20 p-5 rounded-2xl">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-semibold text-slate-400">Kho Bài Mẫu Chuẩn</span>
                  <div className="w-8 h-8 rounded-lg bg-amber-500/10 text-amber-400 flex items-center justify-center">
                    <Dumbbell className="w-4 h-4" />
                  </div>
                </div>
                <div className="text-2xl font-black text-white">{exercises.length} Bài Mẫu Chuẩn</div>
                <p className="text-[11px] text-slate-500 mt-1">Căn cứ trích xuất Pose 3D & FastDTW</p>
              </div>

              <div className="bg-slate-900/80 border border-blue-500/20 p-5 rounded-2xl">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-semibold text-slate-400">Khóa Học Phụ Trách</span>
                  <div className="w-8 h-8 rounded-lg bg-blue-500/10 text-blue-400 flex items-center justify-center">
                    <GraduationCap className="w-4 h-4" />
                  </div>
                </div>
                <div className="text-2xl font-black text-white">1 Khóa Trực Tuyến</div>
                <p className="text-[11px] text-slate-500 mt-1">Tối đa 500 Học viên (Slide 25)</p>
              </div>

              <div className="bg-slate-900/80 border border-emerald-500/20 p-5 rounded-2xl">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-semibold text-slate-400">Hệ Thống Đánh Giá Tự Động</span>
                  <div className="w-8 h-8 rounded-lg bg-emerald-500/10 text-emerald-400 flex items-center justify-center">
                    <ShieldCheck className="w-4 h-4" />
                  </div>
                </div>
                <div className="text-2xl font-black text-white">FastDTW AI Bot</div>
                <p className="text-[11px] text-slate-500 mt-1">Tự động nắn chỉnh góc khớp và chấm điểm</p>
              </div>
            </div>
          </div>
        </section>
      ) : isAuthenticated ? (
        <section className="relative overflow-hidden pt-12 pb-16 px-4 sm:px-6 lg:px-8 border-b border-emerald-500/20 bg-gradient-to-b from-emerald-950/20 via-slate-900/60 to-slate-950">
          <div className="max-w-6xl mx-auto space-y-6">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div>
                <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-bold mb-2">
                  <span>🎓</span>
                  <span>KHÔNG GIAN LUYỆN TẬP HỌC VIÊN</span>
                </div>
                <h1 className="text-3xl sm:text-4xl font-black text-white">
                  Chào mừng học viên, {user?.full_name || user?.username}!
                </h1>
                <p className="text-slate-400 text-xs sm:text-sm mt-1">
                  Chọn bài tập mẫu của Thầy/Cô, quay video thực hiện (1 hoặc 2 góc quay) để nhận điểm và nắn chỉnh góc khớp từ AI.
                </p>
              </div>

              <div className="flex items-center gap-3">
                <Link
                  href="/exercises"
                  className="flex items-center gap-2 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-bold px-5 py-3 rounded-2xl shadow-xl shadow-emerald-500/20 transition active:scale-95 text-xs sm:text-sm"
                >
                  <Dumbbell className="w-4 h-4" />
                  Luyện Tập Ngay
                </Link>
                <Link
                  href="/courses"
                  className="flex items-center gap-2 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 font-semibold px-4 py-3 rounded-2xl transition text-xs sm:text-sm"
                >
                  <GraduationCap className="w-4 h-4" />
                  Đăng Ký Khóa Học
                </Link>
              </div>
            </div>

            {/* Student Metrics */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-5 pt-4">
              <div className="bg-slate-900/80 border border-emerald-500/20 p-5 rounded-2xl">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-semibold text-slate-400">Quy Chuẩn Bài Nộp</span>
                  <div className="w-8 h-8 rounded-lg bg-emerald-500/10 text-emerald-400 flex items-center justify-center">
                    <Video className="w-4 h-4" />
                  </div>
                </div>
                <div className="text-xl font-black text-white">Dual-Camera AI</div>
                <p className="text-[11px] text-slate-500 mt-1">Hỗ trợ 2 góc quay Trái / Phải (Slide 6)</p>
              </div>

              <div className="bg-slate-900/80 border border-blue-500/20 p-5 rounded-2xl">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-semibold text-slate-400">Phản Hồi AI Tự Động</span>
                  <div className="w-8 h-8 rounded-lg bg-blue-500/10 text-blue-400 flex items-center justify-center">
                    <Sparkles className="w-4 h-4" />
                  </div>
                </div>
                <div className="text-xl font-black text-white">Auto-Comment Bot</div>
                <p className="text-[11px] text-slate-500 mt-1">Tự động nhận xét & nắn góc khớp khi có bài nộp</p>
              </div>

              <div className="bg-slate-900/80 border border-purple-500/20 p-5 rounded-2xl">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-semibold text-slate-400">Mạng Xã Hội Luyện Tập</span>
                  <div className="w-8 h-8 rounded-lg bg-purple-500/10 text-purple-400 flex items-center justify-center">
                    <Users className="w-4 h-4" />
                  </div>
                </div>
                <div className="text-xl font-black text-white">Cộng Đồng Luyện Tập</div>
                <p className="text-[11px] text-slate-500 mt-1">Giao lưu, hỏi bài và nhận góp ý từ HLV</p>
              </div>
            </div>
          </div>
        </section>
      ) : (
        <section className="relative overflow-hidden pt-16 pb-20 md:pt-24 md:pb-32 px-4 sm:px-6 lg:px-8 border-b border-slate-800/80">
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_80%_80%_at_50%_-20%,rgba(59,130,246,0.15),rgba(255,255,255,0))]" />
          
          <div className="max-w-5xl mx-auto text-center relative z-10 space-y-6">
            <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-blue-500/10 border border-blue-500/20 text-blue-400 text-xs font-semibold">
              <Zap className="w-3.5 h-3.5" />
              AI Motion Coach Thế Hệ Mới
            </div>

            <h1 className="text-4xl md:text-6xl font-black tracking-tight text-white leading-tight">
              Đánh Giá Kỹ Năng Vận Động <br />
              <span className="bg-gradient-to-r from-blue-400 via-emerald-400 to-indigo-400 bg-clip-text text-transparent">
                Chính Xác Bằng AI & DTW
              </span>
            </h1>

            <p className="max-w-2xl mx-auto text-base md:text-lg text-slate-400 leading-relaxed">
              Hệ thống chấm điểm động tác qua video tự động: Trích xuất Pose 3D (TCPFormer), 
              đồng bộ hóa phi tuyến tính thời gian thực (FastDTW), phát hiện sai lệch góc khớp và chia sẻ cộng đồng.
            </p>

            <div className="flex flex-wrap items-center justify-center gap-4 pt-4">
              <Link
                href="/exercises"
                className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white font-semibold px-6 py-3.5 rounded-2xl shadow-xl shadow-blue-500/25 transition active:scale-95 text-sm"
              >
                <Dumbbell className="w-4 h-4" />
                Khám Phá Bài Tập
              </Link>
              <Link
                href="/feed"
                className="flex items-center gap-2 bg-slate-900 hover:bg-slate-800 text-slate-200 border border-slate-700 font-semibold px-6 py-3.5 rounded-2xl transition active:scale-95 text-sm"
              >
                <Users className="w-4 h-4" />
                Bản Tin Cộng Đồng
              </Link>
            </div>
          </div>

          {/* Feature Highlights Grid */}
          <div className="max-w-6xl mx-auto grid grid-cols-1 md:grid-cols-3 gap-6 mt-16">
            <div className="bg-slate-900/60 border border-slate-800/80 p-6 rounded-2xl">
              <div className="w-10 h-10 rounded-xl bg-blue-500/10 text-blue-400 border border-blue-500/20 flex items-center justify-center mb-4">
                <Activity className="w-5 h-5" />
              </div>
              <h3 className="text-white font-bold text-base mb-2">Đồng Bộ FastDTW</h3>
              <p className="text-slate-400 text-xs leading-relaxed">
                Căn chỉnh thời gian phi tuyến tính giữa học viên và huấn luyện viên, loại bỏ ảnh hưởng của tốc độ thực hiện nhanh/chậm.
              </p>
            </div>

            <div className="bg-slate-900/60 border border-slate-800/80 p-6 rounded-2xl">
              <div className="w-10 h-10 rounded-xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center justify-center mb-4">
                <ShieldCheck className="w-5 h-5" />
              </div>
              <h3 className="text-white font-bold text-base mb-2">Phát Hiện Lỗi Góc Khớp</h3>
              <p className="text-slate-400 text-xs leading-relaxed">
                Tự động khoanh vùng từng frame bị lệch góc khuỷu tay, đầu gối, lưng kèm theo số độ sai lệch cụ thể.
              </p>
            </div>

            <div className="bg-slate-900/60 border border-slate-800/80 p-6 rounded-2xl">
              <div className="w-10 h-10 rounded-xl bg-purple-500/10 text-purple-400 border border-purple-500/20 flex items-center justify-center mb-4">
                <Users className="w-5 h-5" />
              </div>
              <h3 className="text-white font-bold text-base mb-2">Mạng Xã Hội Luyện Tập</h3>
              <p className="text-slate-400 text-xs leading-relaxed">
                Chia sẻ kết quả đánh giá AI, gắn link video bài nộp, nhận góp ý từ HLV và học hỏi lẫn nhau trong cộng đồng.
              </p>
            </div>
          </div>
        </section>
      )}

      {/* Featured Exercises Section */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h2 className="text-2xl font-bold text-white">
              {isCoach ? "Bài Tập Mẫu HLV Tiêu Biểu" : "Bài Tập Luyện Tập Tiêu Biểu"}
            </h2>
            <p className="text-slate-400 text-xs mt-1">
              {isCoach
                ? "Các bài tập đối sánh do Huấn luyện viên tạo ra cho học viên"
                : "Lựa chọn bài tập mẫu và tải lên video để được chấm điểm tự động"}
            </p>
          </div>
          <Link
            href="/exercises"
            className="flex items-center gap-1.5 text-blue-400 hover:text-blue-300 text-xs font-semibold transition"
          >
            <span>Xem tất cả</span>
            <ArrowRight className="w-4 h-4" />
          </Link>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {exercises.map((ex) => (
            <ExerciseCard key={ex.id} exercise={ex} onOpenUpload={handleOpenUpload} />
          ))}
        </div>
      </section>

      {/* Upload Modal Dành Cho Học Viên */}
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
            loadExercises();
          }}
        />
      )}
    </div>
  );
}