"use client";

import { useRef, useState, useEffect, useCallback } from "react";

interface UseDualSyncVideoOptions {
  warpingPath?: [number, number][]; // Ánh xạ [coach_frame, student_frame] từ DTW
  fps?: number;                      // Tần số khung hình chuẩn (mặc định 30fps)
}

export function useDualSyncVideo(options: UseDualSyncVideoOptions = {}) {
  const { warpingPath = [], fps = 30 } = options;

  const coachRef = useRef<HTMLVideoElement | null>(null);
  const studentRef = useRef<HTMLVideoElement | null>(null);

  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [currentTime, setCurrentTime] = useState<number>(0);
  const [duration, setDuration] = useState<number>(0);
  const [playbackRate, setPlaybackRate] = useState<number>(1);
  const isSyncingRef = useRef<boolean>(false);

  // Tạo lookup map từ student frame sang coach frame từ Warping Path
  const studentToCoachFrameMap = useRef<Map<number, number>>(new Map());

  useEffect(() => {
    const map = new Map<number, number>();
    if (warpingPath && warpingPath.length > 0) {
      for (const [cFrame, sFrame] of warpingPath) {
        if (!map.has(sFrame)) {
          map.set(sFrame, cFrame);
        }
      }
    }
    studentToCoachFrameMap.current = map;
  }, [warpingPath]);

  // Đồng bộ vị trí thời gian của HLV dựa theo thời gian bài tập của Học viên
  const syncCoachToStudentTime = useCallback((studentTimeSec: number) => {
    if (!coachRef.current || !studentRef.current || isSyncingRef.current) return;

    const studentDuration = studentRef.current.duration || 1;
    const coachDuration = coachRef.current.duration || 1;

    let targetCoachTime = 0;

    if (studentToCoachFrameMap.current.size > 0) {
      // Dùng DTW Warping Path mapping chính xác
      const currentStudentFrame = Math.round(studentTimeSec * fps);
      const mappedCoachFrame = studentToCoachFrameMap.current.get(currentStudentFrame);

      if (mappedCoachFrame !== undefined) {
        targetCoachTime = mappedCoachFrame / fps;
      } else {
        // Nội suy tuyến tính theo tỉ lệ phần trăm
        targetCoachTime = (studentTimeSec / studentDuration) * coachDuration;
      }
    } else {
      // Đồng bộ theo tỉ lệ phần trăm độ dài video khi chưa có warping path
      targetCoachTime = (studentTimeSec / studentDuration) * coachDuration;
    }

    // Chỉ cập nhật nếu lệch > 0.08 giây (tránh giật hình do can thiệp liên tục)
    if (Math.abs(coachRef.current.currentTime - targetCoachTime) > 0.08) {
      isSyncingRef.current = true;
      coachRef.current.currentTime = Math.min(targetCoachTime, coachDuration);
      setTimeout(() => {
        isSyncingRef.current = false;
      }, 40);
    }
  }, [fps]);

  const togglePlay = useCallback(() => {
    if (!coachRef.current || !studentRef.current) return;

    if (isPlaying) {
      coachRef.current.pause();
      studentRef.current.pause();
      setIsPlaying(false);
    } else {
      // Đảm bảo đồng bộ trước khi phát
      syncCoachToStudentTime(studentRef.current.currentTime);
      coachRef.current.play().catch(() => {});
      studentRef.current.play().catch(() => {});
      setIsPlaying(true);
    }
  }, [isPlaying, syncCoachToStudentTime]);

  const handleSeek = useCallback((newTimeSec: number) => {
    if (!studentRef.current || !coachRef.current) return;

    studentRef.current.currentTime = newTimeSec;
    syncCoachToStudentTime(newTimeSec);
    setCurrentTime(newTimeSec);
  }, [syncCoachToStudentTime]);

  const handleRestart = useCallback(() => {
    if (!coachRef.current || !studentRef.current) return;

    coachRef.current.currentTime = 0;
    studentRef.current.currentTime = 0;
    setCurrentTime(0);
    coachRef.current.play().catch(() => {});
    studentRef.current.play().catch(() => {});
    setIsPlaying(true);
  }, []);

  const changePlaybackRate = useCallback((rate: number) => {
    if (!coachRef.current || !studentRef.current) return;
    coachRef.current.playbackRate = rate;
    studentRef.current.playbackRate = rate;
    setPlaybackRate(rate);
  }, []);

  // Lắng nghe sự kiện cập nhật thời gian từ video học viên (video chủ đạo)
  useEffect(() => {
    const student = studentRef.current;
    if (!student) return;

    const onTimeUpdate = () => {
      setCurrentTime(student.currentTime);
      syncCoachToStudentTime(student.currentTime);
    };

    const onLoadedMetadata = () => {
      setDuration(student.duration || 0);
    };

    const onEnded = () => {
      setIsPlaying(false);
      if (coachRef.current) {
        coachRef.current.pause();
      }
    };

    student.addEventListener("timeupdate", onTimeUpdate);
    student.addEventListener("loadedmetadata", onLoadedMetadata);
    student.addEventListener("ended", onEnded);

    return () => {
      student.removeEventListener("timeupdate", onTimeUpdate);
      student.removeEventListener("loadedmetadata", onLoadedMetadata);
      student.removeEventListener("ended", onEnded);
    };
  }, [syncCoachToStudentTime]);

  return {
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
  };
}
