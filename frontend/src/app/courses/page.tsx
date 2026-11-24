"use client";

import React, { useState, useEffect } from "react";
import { GraduationCap, Users, UserCheck, Search, Plus, Sparkles, BookOpen, Clock, Check, X } from "lucide-react";
import { Course } from "../../types/course";
import { courseService } from "../../services/apiClient";
import { call } from "../../services/api";
import { useAuth } from "../../hooks/useAuth";

export default function CoursesPage() {
  const { user, isCoach, isAuthenticated } = useAuth();
  const [courses, setCourses] = useState<Course[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [enrolledIds, setEnrolledIds] = useState<number[]>([]);
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);
  const [newTitle, setNewTitle] = useState<string>("");
  const [newDesc, setNewDesc] = useState<string>("");
  const [createMsg, setCreateMsg] = useState<string | null>(null);
  // Trạng thái đăng ký của HV theo id khóa học: PENDING (chờ GV duyệt) | APPROVED | REJECTED
  const [statusById, setStatusById] = useState<Record<number, string>>({});
  const [requests, setRequests] = useState<any[]>([]);

  const loadMyStatus = () => {
    if (!isAuthenticated) return;
    call<any[]>("get_list_courses", { index: 0, count: 100 })
      .then((list) => setStatusById(Object.fromEntries(list.filter((c) => c.my_status).map((c) => [c.internal_id, c.my_status]))))
      .catch(() => {});
  };

  const loadRequests = () => {
    if (!isCoach) return;
    call<any[]>("get_requested_enrollment", { index: 0, count: 100 }).then(setRequests).catch(() => setRequests([]));
  };

  useEffect(() => {
    loadMyStatus();
    loadRequests();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAuthenticated, isCoach]);

  const handleDecision = async (studentId: number, accept: boolean) => {
    try {
      await call("set_approve_enrollment", { user_id: studentId, is_accept: accept ? 1 : 0 });
      loadRequests();
    } catch (err: any) {
      alert(err?.message || "Không thể xử lý yêu cầu.");
    }
  };

  useEffect(() => {
    loadCourses();
  }, []);

  const loadCourses = async () => {
    setIsLoading(true);
    try {
      const data = await courseService.getCourses();
      setCourses(data);
    } catch {
      setCourses([]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleEnroll = async (courseId: number) => {
    try {
      await courseService.enrollCourse(courseId);
      setStatusById((prev) => ({ ...prev, [courseId]: "PENDING" }));
      alert("Đã gửi yêu cầu tham gia, vui lòng chờ giáo viên duyệt.");
    } catch (err: any) {
      alert(err?.response?.data?.detail || "Bạn đã gửi yêu cầu / đã tham gia lớp học này hoặc lớp đã đủ 500 học viên.");
    }
  };

  const handleCreateCourse = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreateMsg(null);
    try {
      await courseService.createCourse(newTitle, newDesc);
      setIsModalOpen(false);
      setNewTitle("");
      setNewDesc("");
      loadCourses();
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      setCreateMsg(typeof detail === "object" ? detail.message : detail || "Mỗi giáo viên chỉ được tạo tối đa 01 khóa học.");
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in text-white">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8">
        <div>
          <div className="flex items-center gap-2 text-blue-400 text-xs font-semibold uppercase tracking-wider mb-1">
            <GraduationCap className="w-4 h-4" />
            <span>Quản Lý Lớp Học Trực Tuyến (Slide 25 & 27)</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-white">
            Danh Sách Khóa Học & Lớp Giảng Viên
          </h1>
          <p className="text-slate-400 text-xs sm:text-sm mt-1">
            Mỗi giáo viên quản lý tối đa 01 lớp học trực tuyến (tối đa 500 học viên).
          </p>
        </div>

        {isCoach && (
          <button
            onClick={() => setIsModalOpen(true)}
            className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white font-semibold text-xs py-2.5 px-4 rounded-xl transition shadow-lg shadow-blue-500/20"
          >
            <Plus className="w-4 h-4" />
            Tạo Khóa Học Của Tôi
          </button>
        )}
      </div>

      {/* Yêu cầu tham gia lớp (GV duyệt) */}
      {isCoach && (
        <div className="bg-slate-900/90 rounded-2xl border border-slate-800 p-6 mb-8 shadow-xl">
          <h2 className="text-sm font-bold text-white flex items-center gap-2 mb-3">
            <Clock className="w-4 h-4 text-amber-400" />
            Yêu Cầu Tham Gia Lớp Của Bạn ({requests.length})
          </h2>
          {requests.length === 0 ? (
            <p className="text-xs text-slate-500">Không có yêu cầu nào đang chờ duyệt.</p>
          ) : (
            <div className="space-y-2">
              {requests.map((r) => (
                <div key={r.id} className="flex items-center justify-between gap-3 bg-slate-950 p-3 rounded-xl border border-slate-800">
                  <a href={`/profile/${r.id}`} className="text-xs font-semibold text-slate-200 hover:underline">
                    {r.name || r.username}
                  </a>
                  <div className="flex gap-2">
                    <button onClick={() => handleDecision(r.id, true)} className="flex items-center gap-1 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold px-3 py-1.5 rounded-lg transition">
                      <Check className="w-3.5 h-3.5" /> Chấp nhận
                    </button>
                    <button onClick={() => handleDecision(r.id, false)} className="flex items-center gap-1 bg-slate-800 hover:bg-rose-950/60 text-slate-300 hover:text-rose-400 text-xs font-semibold px-3 py-1.5 rounded-lg border border-slate-700 transition">
                      <X className="w-3.5 h-3.5" /> Từ chối
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Danh sách khóa học */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {courses.map((course) => {
          const status = statusById[course.id] || (enrolledIds.includes(course.id) ? "PENDING" : undefined);
          const isEnrolled = status === "APPROVED" || status === "PENDING";
          return (
            <div
              key={course.id}
              className="bg-slate-900/90 rounded-2xl border border-slate-800 p-6 flex flex-col justify-between hover:border-slate-700 transition shadow-xl"
            >
              <div>
                <div className="flex items-center justify-between mb-3">
                  <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20">
                    <BookOpen className="w-3.5 h-3.5" />
                    Mã Lớp #{course.id}
                  </span>
                  <span className="text-[11px] text-slate-500 flex items-center gap-1">
                    <Users className="w-3 h-3" />
                    Tối đa {course.max_students} HV
                  </span>
                </div>

                <h3 className="text-lg font-bold text-white mb-2">{course.title}</h3>
                <p className="text-slate-400 text-xs line-clamp-3 leading-relaxed mb-4">
                  {course.description || "Khóa huấn luyện chuyên sâu với các bài tập mẫu chuẩn xác."}
                </p>

                <div className="bg-slate-950 p-3 rounded-xl border border-slate-800 mb-4">
                  <p className="text-[11px] text-slate-400">Giáo viên phụ trách:</p>
                  <p className="text-xs font-semibold text-slate-200">
                    {course.teacher?.full_name || course.teacher?.username || `Giáo viên #${course.teacher_id}`}
                  </p>
                </div>
              </div>

              <div className="pt-4 border-t border-slate-800/80">
                {isCoach ? (
                  course.teacher_id === user?.id ? (
                    <div className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl text-xs font-bold bg-amber-500/20 text-amber-300 border border-amber-500/40">
                      <span>🎖️</span>
                      <span>Lớp Do Bạn Phụ Trách Giảng Dạy</span>
                    </div>
                  ) : (
                    <div className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl text-xs font-medium bg-slate-800/60 text-slate-400 border border-slate-700/60">
                      <span>Lớp Của Giảng Viên Khác</span>
                    </div>
                  )
                ) : (
                  <button
                    onClick={() => handleEnroll(course.id)}
                    disabled={isEnrolled}
                    className={`w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl text-xs font-semibold transition ${
                      status === "APPROVED"
                        ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                        : status === "PENDING"
                        ? "bg-amber-500/20 text-amber-300 border border-amber-500/30"
                        : "bg-blue-600 hover:bg-blue-500 text-white shadow-md shadow-blue-500/20"
                    }`}
                  >
                    {status === "APPROVED" ? (
                      <>
                        <UserCheck className="w-4 h-4" />
                        Đã Tham Gia Lớp
                      </>
                    ) : status === "PENDING" ? (
                      <>
                        <Clock className="w-4 h-4" />
                        Chờ Giáo Viên Duyệt
                      </>
                    ) : status === "REJECTED" ? (
                      "Bị Từ Chối - Gửi Lại Yêu Cầu"
                    ) : (
                      "Đăng Ký Tham Gia Lớp Này"
                    )}
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Modal Tạo Khóa Học cho GV */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
          <div className="bg-slate-900 border border-slate-800 rounded-3xl max-w-md w-full p-6 shadow-2xl">
            <h2 className="text-lg font-bold text-white mb-1">Tạo Khóa Học Trực Tuyến</h2>
            <p className="text-xs text-slate-400 mb-4">
              Theo quy định Slide 25: Mỗi Giáo viên chỉ được tạo tối đa 01 khóa học (500 HV).
            </p>

            {createMsg && (
              <div className="mb-4 p-3 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-xs">
                {createMsg}
              </div>
            )}

            <form onSubmit={handleCreateCourse} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Tên Khóa Học</label>
                <input
                  type="text"
                  required
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  placeholder="Ví dụ: Lớp Huấn Luyện Điều Lệnh K65"
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-white focus:outline-none focus:border-blue-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Mô tả Khóa Học</label>
                <textarea
                  value={newDesc}
                  onChange={(e) => setNewDesc(e.target.value)}
                  placeholder="Mô tả mục tiêu và nội dung khóa học..."
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-white focus:outline-none focus:border-blue-500 resize-none h-20"
                />
              </div>

              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="flex-1 bg-slate-800 text-slate-300 text-xs font-semibold py-2.5 rounded-xl hover:bg-slate-700 transition"
                >
                  Hủy
                </button>
                <button
                  type="submit"
                  className="flex-1 bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold py-2.5 rounded-xl transition shadow-md shadow-blue-500/20"
                >
                  Tạo Khóa Học
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
