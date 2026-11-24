"use client";

import React, { useState, useEffect } from "react";
import { Play, Pause, RotateCcw, Award, AlertTriangle, CheckCircle, Video, Sliders } from "lucide-react";
import confetti from "canvas-confetti";
import { useDualSyncVideo } from "../../hooks/useDualSyncVideo";
import { FrameError } from "../../types/submission";
import { getVideoUrl } from "../../utils/media";

interface DualVideoPlayerProps {
  coachVideoUrl: string;
  studentVideoUrl: string;
  fusedVideoUrl?: string;
  score?: number;
  feedback?: string;
  warpingPath?: [number, number][];
  errors?: FrameError[];
}

export const DualVideoPlayer: React.FC<DualVideoPlayerProps> = ({
  coachVideoUrl,
  studentVideoUrl,
  fusedVideoUrl,
  score,
  feedback,
  warpingPath,
  errors = [],
}) => {
  const [viewMode, setViewMode] = useState<"dual" | "fused">("dual");
  const {
    coachRef,
    studentRef,
    isPlaying,
    currentTime,
    duration,
    playbackRate,
    togglePlay,
    handleSeek,
    handleRestart,
    changePlaybackRate,
  } = useDualSyncVideo({
    warpingPath,
    fps: 30,
  });

  // Bắn pháo hoa ăn mừng khi điểm cao
  useEffect(() => {
    if (score && score >= 85) {
      confetti({
        particleCount: 80,
        spread: 70,
        origin: { y: 0.6 },
      });
    }
  }, [score]);

  const formatTime = (timeInSec: number) => {
    const mins = Math.floor(timeInSec / 60);
    const secs = Math.floor(timeInSec % 60);
    return `${mins}:${secs < 10 ? "0" : ""}${secs}`;
  };

  const currentFrame = Math.round(currentTime * 30);
  const activeError = errors.find((err) => Math.abs(err.student_frame - currentFrame) <= 5);

  return (
    <div className="bg-slate-900 text-white rounded-2xl p-6 shadow-2xl max-w-5xl mx-auto border border-slate-800">
      {/* Header Điểm số & Chuyển chế độ xem */}
      <div className="flex flex-wrap justify-between items-center mb-6 pb-4 border-b border-slate-800 gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-xl md:text-2xl font-bold bg-gradient-to-r from-blue-400 to-emerald-400 bg-clip-text text-transparent">
              Đánh giá Động tác & Phân tích AI
            </h2>
            <span className="text-xs bg-blue-500/10 text-blue-400 border border-blue-500/20 px-2 py-0.5 rounded-full font-medium">
              DTW Sync Active
            </span>
          </div>
          <p className="text-sm text-slate-400 mt-1">
            Đồng bộ hóa phi tuyến tính thời gian thực bài tập học viên với HLV chuẩn
          </p>
        </div>

        <div className="flex items-center gap-3">
          {fusedVideoUrl && (
            <div className="flex bg-slate-800 p-1 rounded-lg border border-slate-700 text-xs font-semibold">
              <button
                onClick={() => setViewMode("dual")}
                className={`px-3 py-1.5 rounded-md transition ${viewMode === "dual" ? "bg-blue-600 text-white" : "text-slate-400 hover:text-white"}`}
              >
                Song song (Dual)
              </button>
              <button
                onClick={() => setViewMode("fused")}
                className={`px-3 py-1.5 rounded-md transition ${viewMode === "fused" ? "bg-blue-600 text-white" : "text-slate-400 hover:text-white"}`}
              >
                Ghép AI (Fused)
              </button>
            </div>
          )}

          {score !== undefined && (
            <div className={`flex items-center gap-2 px-4 py-2 rounded-xl border ${
              score >= 80 ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/30" :
              score >= 60 ? "bg-amber-500/20 text-amber-400 border-amber-500/30" :
              "bg-rose-500/20 text-rose-400 border-rose-500/30"
            }`}>
              <Award className="w-6 h-6" />
              <div>
                <span className="text-2xl font-black">{score}</span>
                <span className="text-xs opacity-75">/100</span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Vùng hiển thị Video */}
      {viewMode === "dual" ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Video HLV Chuẩn */}
          <div className="relative rounded-xl overflow-hidden bg-black border border-slate-800 shadow-inner group">
            <div className="absolute top-3 left-3 z-10 bg-emerald-600/90 backdrop-blur-sm text-xs px-2.5 py-1 rounded-md font-semibold flex items-center gap-1 shadow">
              <CheckCircle className="w-3.5 h-3.5" />
              HLV (Bài Mẫu)
            </div>
            <video
              ref={coachRef}
              src={getVideoUrl(coachVideoUrl)}
              className="w-full aspect-video object-cover"
              playsInline
            />
          </div>

          {/* Video Học Viên */}
          <div className="relative rounded-xl overflow-hidden bg-black border border-slate-800 shadow-inner group">
            <div className="absolute top-3 left-3 z-10 bg-blue-600/90 backdrop-blur-sm text-xs px-2.5 py-1 rounded-md font-semibold flex items-center gap-1 shadow">
              <Video className="w-3.5 h-3.5" />
              Học Viên (Bài Nộp)
            </div>

            {/* Cảnh báo lỗi trực tiếp trên khung hình */}
            {activeError && (
              <div className="absolute top-3 right-3 z-10 bg-rose-600/90 backdrop-blur-sm text-xs px-2.5 py-1 rounded-md font-semibold flex items-center gap-1 text-white animate-pulse">
                <AlertTriangle className="w-3.5 h-3.5" />
                Lệch {activeError.max_angle_error}°
              </div>
            )}

            <video
              ref={studentRef}
              src={getVideoUrl(studentVideoUrl)}
              className={`w-full aspect-video object-cover ${activeError ? "ring-2 ring-rose-500" : ""}`}
              playsInline
            />
          </div>
        </div>
      ) : (
        /* Video Fused AI Render */
        <div className="rounded-xl overflow-hidden bg-black border border-slate-800">
          <video
            src={getVideoUrl(fusedVideoUrl)}
            controls
            autoPlay
            className="w-full aspect-[2/1] object-contain mx-auto"
          />
        </div>
      )}

      {/* Điều khiển đồng bộ & Scrub Bar */}
      {viewMode === "dual" && (
        <div className="mt-6 bg-slate-950/60 p-4 rounded-xl border border-slate-800/80">
          {/* Thanh trượt thời gian (Scrubber) */}
          <div className="flex items-center gap-3">
            <span className="text-xs text-slate-400 font-mono w-10 text-right">
              {formatTime(currentTime)}
            </span>
            <div className="relative flex-1 flex items-center">
              <input
                type="range"
                min="0"
                max={duration || 100}
                step="0.05"
                value={currentTime}
                onChange={(e) => handleSeek(parseFloat(e.target.value))}
                className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-blue-500"
              />
            </div>
            <span className="text-xs text-slate-400 font-mono w-10">
              {formatTime(duration)}
            </span>
          </div>

          {/* Các nút bấm điều khiển */}
          <div className="flex flex-wrap items-center justify-between mt-4 pt-2">
            <div className="flex items-center gap-3">
              <button
                onClick={togglePlay}
                className="flex items-center gap-2 px-5 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 active:scale-95 font-medium transition shadow-lg shadow-blue-500/20"
              >
                {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4 fill-white" />}
                <span>{isPlaying ? "Tạm dừng" : "Phát đồng bộ"}</span>
              </button>
              <button
                onClick={handleRestart}
                className="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 active:scale-95 transition text-slate-300"
                title="Xem lại từ đầu"
              >
                <RotateCcw className="w-4 h-4" />
              </button>
            </div>

            {/* Bộ chọn tốc độ phát */}
            <div className="flex items-center gap-2 bg-slate-800 px-3 py-1.5 rounded-lg border border-slate-700 text-xs">
              <Sliders className="w-3.5 h-3.5 text-slate-400" />
              <span className="text-slate-400">Tốc độ:</span>
              {[0.5, 0.75, 1, 1.25].map((rate) => (
                <button
                  key={rate}
                  onClick={() => changePlaybackRate(rate)}
                  className={`px-1.5 py-0.5 rounded transition ${playbackRate === rate ? "bg-blue-600 text-white font-bold" : "text-slate-400 hover:text-white"}`}
                >
                  {rate}x
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Nhận xét AI & Bảng chi tiết lỗi góc khớp */}
      <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="md:col-span-2 p-4 rounded-xl bg-slate-950/60 border border-slate-800">
          <h4 className="font-semibold text-sm text-slate-200 mb-2 flex items-center gap-2">
            <Award className="w-4 h-4 text-blue-400" />
            Nhận xét chi tiết từ AI Motion Coach:
          </h4>
          <p className="text-slate-300 text-sm leading-relaxed whitespace-pre-line">
            {feedback || "Chưa có nhận xét. Bài tập đang trong hàng đợi xử lý."}
          </p>
        </div>

        <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800">
          <h4 className="font-semibold text-sm text-slate-200 mb-2 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-400" />
            Thời điểm sai lệch ({errors.length}):
          </h4>
          <div className="max-h-28 overflow-y-auto space-y-1.5 pr-1 text-xs">
            {errors.length === 0 ? (
              <p className="text-emerald-400">Không có sai lệch đáng kể! Động tác chuẩn.</p>
            ) : (
              errors.map((err, idx) => (
                <button
                  key={idx}
                  onClick={() => handleSeek(err.student_frame / 30)}
                  className="w-full text-left p-1.5 rounded bg-slate-800/80 hover:bg-slate-700 transition flex justify-between items-center text-slate-300"
                >
                  <span>Frame {err.student_frame} ({formatTime(err.student_frame / 30)})</span>
                  <span className="text-rose-400 font-semibold">+{err.max_angle_error}°</span>
                </button>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
