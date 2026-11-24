"use client";

import React from "react";
import Link from "next/link";
import { Play, UploadCloud, Shield, Sparkles, Flame, Settings } from "lucide-react";
import { Exercise } from "../../types/exercise";
import { useAuth } from "../../hooks/useAuth";

interface ExerciseCardProps {
  exercise: Exercise;
  onOpenUpload?: (exercise: Exercise) => void;
}

export const ExerciseCard: React.FC<ExerciseCardProps> = ({ exercise, onOpenUpload }) => {
  const { isCoach } = useAuth();

  const getCategoryBadge = (category: string) => {
    switch (category) {
      case "military":
        return {
          label: "Điều lệnh Quân sự",
          icon: Shield,
          color: "bg-emerald-500/20 text-emerald-300 border-emerald-500/30",
        };
      case "sword_dance":
        return {
          label: "Múa kiếm cổ phong",
          icon: Flame,
          color: "bg-amber-500/20 text-amber-300 border-amber-500/30",
        };
      default:
        return {
          label: "Vũ đạo nghệ thuật",
          icon: Sparkles,
          color: "bg-purple-500/20 text-purple-300 border-purple-500/30",
        };
    }
  };

  const badge = getCategoryBadge(exercise.category);
  const BadgeIcon = badge.icon;

  return (
    <div className="bg-slate-900/90 rounded-2xl border border-slate-800 p-5 hover:border-slate-700 hover:shadow-xl hover:shadow-blue-500/5 transition duration-300 flex flex-col justify-between group">
      <div>
        <div className="flex items-center justify-between mb-3">
          <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold border ${badge.color}`}>
            <BadgeIcon className="w-3.5 h-3.5" />
            {badge.label}
          </span>
          <span className="text-[11px] text-slate-500">ID: #{exercise.id}</span>
        </div>

        <h3 className="text-lg font-bold text-white group-hover:text-blue-400 transition mb-2">
          {exercise.title}
        </h3>

        <p className="text-slate-400 text-xs line-clamp-3 leading-relaxed mb-4">
          {exercise.description || "Bài tập rèn luyện kỹ năng vận động chuẩn xác theo hướng dẫn mẫu của Huấn luyện viên."}
        </p>
      </div>

      <div className="pt-4 border-t border-slate-800/80 flex items-center gap-2 mt-auto">
        <Link
          href={`/exercises/${exercise.id}`}
          className="flex-1 flex items-center justify-center gap-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold py-2.5 px-3 rounded-xl transition"
        >
          <Play className="w-3.5 h-3.5" />
          Xem Mẫu
        </Link>

        {/* Phân biệt rõ quyền Huấn luyện viên vs Học viên */}
        {isCoach ? (
          <Link
            href={`/exercises/${exercise.id}`}
            className="flex-1 flex items-center justify-center gap-1.5 bg-amber-500/20 hover:bg-amber-600 border border-amber-500/40 text-amber-300 hover:text-white text-xs font-bold py-2.5 px-3 rounded-xl transition"
          >
            <Settings className="w-3.5 h-3.5" />
            Quản Lý & Bài Nộp
          </Link>
        ) : (
          <button
            onClick={() => onOpenUpload && onOpenUpload(exercise)}
            className="flex-1 flex items-center justify-center gap-1.5 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold py-2.5 px-3 rounded-xl transition shadow-md shadow-emerald-500/20"
          >
            <UploadCloud className="w-3.5 h-3.5" />
            Nộp Bài
          </button>
        )}
      </div>
    </div>
  );
};
