"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { Activity, LogIn, UserPlus, Shield, User, Lock, Mail, AlertCircle, Loader2 } from "lucide-react";
import { useAuth } from "../../hooks/useAuth";
import { UserRole } from "../../types/auth";

export default function LoginPage() {
  const router = useRouter();
  const { login, register } = useAuth();

  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [role, setRole] = useState<UserRole>("student");

  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);
    setIsLoading(true);

    try {
      if (mode === "login") {
        await login({ username_or_email: username, password });
      } else {
        await register({
          username,
          email,
          password,
          full_name: fullName || undefined,
          role,
        });
      }
      window.location.href = "/exercises";
    } catch (err: any) {
      const msg = err.response?.data?.detail || "Đã xảy ra lỗi khi xác thực. Vui lòng thử lại.";
      setErrorMessage(typeof msg === "string" ? msg : JSON.stringify(msg));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-[80vh] flex items-center justify-center px-4 py-12">
      <div className="max-w-md w-full bg-slate-900 border border-slate-800 rounded-3xl p-8 shadow-2xl space-y-6">
        {/* Header */}
        <div className="text-center space-y-2">
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-tr from-blue-600 to-emerald-500 flex items-center justify-center mx-auto shadow-lg shadow-blue-500/20">
            <Activity className="w-6 h-6 text-white" />
          </div>
          <h2 className="text-2xl font-black text-white">
            {mode === "login" ? "Đăng Nhập Tài Khoản" : "Đăng Ký Thành Viên"}
          </h2>
          <p className="text-xs text-slate-400">
            {mode === "login"
              ? "Truy cập hệ thống đánh giá kỹ năng vận động bằng AI"
              : "Bắt đầu hành trình rèn luyện chuẩn mực với AI Motion Coach"}
          </p>
        </div>

        {/* Mode Switcher */}
        <div className="flex bg-slate-950 p-1 rounded-xl border border-slate-800 text-xs font-semibold">
          <button
            type="button"
            onClick={() => {
              setMode("login");
              setErrorMessage(null);
            }}
            className={`flex-1 py-2 rounded-lg transition ${mode === "login" ? "bg-blue-600 text-white" : "text-slate-400 hover:text-white"}`}
          >
            Đăng Nhập
          </button>
          <button
            type="button"
            onClick={() => {
              setMode("register");
              setErrorMessage(null);
            }}
            className={`flex-1 py-2 rounded-lg transition ${mode === "register" ? "bg-blue-600 text-white" : "text-slate-400 hover:text-white"}`}
          >
            Tạo Tài Khoản
          </button>
        </div>

        {errorMessage && (
          <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0 text-rose-400" />
            <span>{errorMessage}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4 text-xs">
          <div>
            <label className="block text-slate-300 font-semibold mb-1.5">
              {mode === "login" ? "Tên người dùng hoặc Email" : "Tên tài khoản (Username)"}
            </label>
            <div className="relative">
              <User className="w-4 h-4 text-slate-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                required
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="vd: nguyenvana"
                className="w-full bg-slate-950 border border-slate-800 rounded-xl pl-10 pr-4 py-2.5 text-white placeholder-slate-600 focus:outline-none focus:border-blue-500 transition"
              />
            </div>
          </div>

          {mode === "register" && (
            <>
              <div>
                <label className="block text-slate-300 font-semibold mb-1.5">Địa chỉ Email</label>
                <div className="relative">
                  <Mail className="w-4 h-4 text-slate-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="vd: vana@example.com"
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl pl-10 pr-4 py-2.5 text-white placeholder-slate-600 focus:outline-none focus:border-blue-500 transition"
                  />
                </div>
              </div>

              <div>
                <label className="block text-slate-300 font-semibold mb-1.5">Họ và Tên (Tùy chọn)</label>
                <input
                  type="text"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="vd: Nguyễn Văn A"
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-white placeholder-slate-600 focus:outline-none focus:border-blue-500 transition"
                />
              </div>

              <div>
                <label className="block text-slate-300 font-semibold mb-1.5">Vai trò trong hệ thống</label>
                <div className="grid grid-cols-2 gap-3">
                  <button
                    type="button"
                    onClick={() => setRole("student")}
                    className={`p-2.5 rounded-xl border text-center transition ${
                      role === "student"
                        ? "bg-blue-600/20 text-blue-400 border-blue-500/50 font-bold"
                        : "bg-slate-950 text-slate-400 border-slate-800"
                    }`}
                  >
                    Học Viên (Student)
                  </button>
                  <button
                    type="button"
                    onClick={() => setRole("coach")}
                    className={`p-2.5 rounded-xl border text-center transition ${
                      role === "coach"
                        ? "bg-amber-600/20 text-amber-400 border-amber-500/50 font-bold"
                        : "bg-slate-950 text-slate-400 border-slate-800"
                    }`}
                  >
                    Huấn Luyện Viên (Coach)
                  </button>
                </div>
              </div>
            </>
          )}

          <div>
            <label className="block text-slate-300 font-semibold mb-1.5">Mật khẩu</label>
            <div className="relative">
              <Lock className="w-4 h-4 text-slate-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full bg-slate-950 border border-slate-800 rounded-xl pl-10 pr-4 py-2.5 text-white placeholder-slate-600 focus:outline-none focus:border-blue-500 transition"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-semibold py-3 rounded-xl transition shadow-lg shadow-blue-500/25 active:scale-95 mt-2"
          >
            {isLoading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : mode === "login" ? (
              <>
                <LogIn className="w-4 h-4" />
                Đăng Nhập
              </>
            ) : (
              <>
                <UserPlus className="w-4 h-4" />
                Tạo Tài Khoản
              </>
            )}
          </button>
        </form>
      </div>
    </div>
  );
}
