"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity, Dumbbell, Users, Video, LogIn, LogOut, User as UserIcon, Menu, X, GraduationCap, Plus, Award, Bell, MessageCircle, Search, Settings, Shield } from "lucide-react";
import { useAuth } from "../../hooks/useAuth";
import { call } from "../../services/api";
import { CreateExerciseModal } from "../exercise/CreateExerciseModal";

export const Navbar: React.FC = () => {
  const pathname = usePathname();
  const { user, tokenData, isAuthenticated, isCoach, isAdmin, logout } = useAuth();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [isExerciseModalOpen, setIsExerciseModalOpen] = useState(false);
  const [badge, setBadge] = useState(0);
  const [unreadChats, setUnreadChats] = useState(0);

  // Số thông báo / tin nhắn chưa đọc, cập nhật định kỳ
  useEffect(() => {
    if (!isAuthenticated) return;
    const poll = () => {
      call<any>("get_notification", { index: 0, count: 1 }).then((n) => setBadge(n.badge)).catch(() => {});
      call<any>("get_list_conversation", { index: 0, count: 1 }).then((c) => setUnreadChats(c.numNewMessage)).catch(() => {});
    };
    poll();
    const t = setInterval(poll, 20000);
    return () => clearInterval(t);
  }, [isAuthenticated]);

  const iconLinks = [
    { href: "/search", label: "Tìm kiếm", icon: Search, count: 0 },
    { href: "/messages", label: "Tin nhắn", icon: MessageCircle, count: unreadChats },
    { href: "/notifications", label: "Thông báo", icon: Bell, count: badge },
    { href: "/settings", label: "Cài đặt", icon: Settings, count: 0 },
    ...(isAdmin ? [{ href: "/admin", label: "Quản trị", icon: Shield, count: 0 }] : []),
  ];

  // Dynamic Navigation Links theo vai trò
  const navLinks = [
    { href: "/", label: "Tổng Quan", icon: Activity },
    {
      href: "/courses",
      label: isCoach ? "Lớp Giảng Dạy" : "Khóa Học",
      icon: GraduationCap,
    },
    {
      href: "/exercises",
      label: isCoach ? "Quản Lý Bài Tập" : "Luyện Tập & Nộp Bài",
      icon: Dumbbell,
    },
    { href: "/feed", label: "Cộng Đồng", icon: Users },
  ];

  return (
    <>
      <nav className="sticky top-0 z-50 bg-slate-900/90 backdrop-blur-md border-b border-slate-800 text-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            {/* Logo Brand */}
            <Link href="/" className="flex items-center gap-2.5 font-bold text-lg tracking-tight">
              <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-blue-600 to-emerald-500 flex items-center justify-center shadow-lg shadow-blue-500/20">
                <Activity className="w-5 h-5 text-white" />
              </div>
              <span className="hidden xl:inline whitespace-nowrap bg-gradient-to-r from-white via-slate-200 to-slate-400 bg-clip-text text-transparent">
                MotionAI Coach
              </span>
            </Link>

            {/* Desktop Nav Items */}
            <div className="hidden md:flex items-center gap-1">
              {navLinks.map((link) => {
                const Icon = link.icon;
                const isActive = pathname === link.href;
                return (
                  <Link
                    key={link.href}
                    href={link.href}
                    title={link.label}
                    className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-sm font-medium transition ${
                      isActive
                        ? "bg-blue-600/20 text-blue-400 border border-blue-500/30 shadow-inner"
                        : "text-slate-300 hover:text-white hover:bg-slate-800/60"
                    }`}
                  >
                    <Icon className="w-4 h-4" />
                    <span className="hidden xl:inline whitespace-nowrap">{link.label}</span>
                  </Link>
                );
              })}
            </div>

            {/* User Auth Section */}
            <div className="hidden md:flex items-center gap-3">
              {isAuthenticated && (user || tokenData) ? (
                <div className="flex items-center gap-3">
                  {/* Tìm kiếm, tin nhắn, thông báo, cài đặt, quản trị */}
                  <div className="flex items-center gap-1">
                    {iconLinks.map(({ href, label, icon: Icon, count }) => (
                      <Link
                        key={href}
                        href={href}
                        title={label}
                        className={`relative p-2 rounded-lg transition border ${
                          pathname?.startsWith(href)
                            ? "bg-blue-600/20 text-blue-400 border-blue-500/30"
                            : "bg-slate-800 text-slate-400 hover:text-white border-slate-700"
                        }`}
                      >
                        <Icon className="w-4 h-4" />
                        {count > 0 && (
                          <span className="absolute -top-1.5 -right-1.5 min-w-[18px] rounded-full bg-rose-500 px-1 text-center text-[10px] font-bold leading-[18px] text-white">
                            {count > 99 ? "99+" : count}
                          </span>
                        )}
                      </Link>
                    ))}
                  </div>

                  {/* Nút đăng bài mẫu nhanh dành riêng cho Huấn Luyện Viên */}
                  {isCoach && (
                    <button
                      onClick={() => setIsExerciseModalOpen(true)}
                      className="flex items-center gap-1.5 bg-gradient-to-r from-amber-600 to-orange-600 hover:from-amber-500 hover:to-orange-500 text-white text-xs font-bold py-1.5 px-3 rounded-xl shadow-md shadow-amber-500/20 transition active:scale-95 border border-amber-400/30"
                    >
                      <Plus className="w-3.5 h-3.5" />
                      + Đăng Bài Mẫu (HLV)
                    </button>
                  )}

                  {/* Huy hiệu vai trò nổi bật (bấm để vào trang cá nhân) */}
                  <Link
                    href={`/profile/${user?.id || tokenData?.user_id}`}
                    title="Trang cá nhân"
                    className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-semibold border ${
                      isCoach
                        ? "bg-amber-500/15 border-amber-500/40 text-amber-300 shadow-sm shadow-amber-500/10"
                        : "bg-emerald-500/15 border-emerald-500/40 text-emerald-300 shadow-sm shadow-emerald-500/10"
                    }`}
                  >
                    <span className="text-sm">{isCoach ? "🎖️" : "🎓"}</span>
                    <span className="hidden xl:inline whitespace-nowrap font-bold text-slate-100">
                      {user?.full_name || user?.username || tokenData?.username}
                    </span>
                    <span
                      className={`whitespace-nowrap px-1.5 py-0.5 rounded text-[10px] font-black uppercase tracking-wider ${
                        isCoach ? "bg-amber-500/30 text-amber-200" : "bg-emerald-500/30 text-emerald-200"
                      }`}
                    >
                      {isAdmin ? "Quản Trị" : isCoach ? "Huấn Luyện Viên" : "Học Viên"}
                    </span>
                  </Link>

                  <button
                    onClick={logout}
                    className="p-2 rounded-lg bg-slate-800 hover:bg-rose-950/60 text-slate-400 hover:text-rose-400 transition border border-slate-700"
                    title="Đăng xuất"
                  >
                    <LogOut className="w-4 h-4" />
                  </button>
                </div>
              ) : (
                <Link
                  href="/login"
                  className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-lg text-sm font-medium transition shadow-md shadow-blue-500/20"
                >
                  <LogIn className="w-4 h-4" />
                  Đăng Nhập
                </Link>
              )}
            </div>

            {/* Mobile Menu Button */}
            <div className="flex md:hidden">
              <button
                onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                className="p-2 rounded-lg bg-slate-800 text-slate-400 hover:text-white"
              >
                {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
              </button>
            </div>
          </div>
        </div>

        {/* Mobile Menu Dropdown */}
        {mobileMenuOpen && (
          <div className="md:hidden border-b border-slate-800 bg-slate-900 px-4 pt-2 pb-4 space-y-2">
            {navLinks.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                onClick={() => setMobileMenuOpen(false)}
                className="block px-3 py-2 rounded-md text-base font-medium text-slate-300 hover:text-white hover:bg-slate-800"
              >
                {link.label}
              </Link>
            ))}
            {isAuthenticated &&
              [{ href: `/profile/${user?.id || tokenData?.user_id}`, label: "Trang cá nhân", count: 0 }, ...iconLinks].map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  onClick={() => setMobileMenuOpen(false)}
                  className="flex items-center justify-between px-3 py-2 rounded-md text-base font-medium text-slate-300 hover:text-white hover:bg-slate-800"
                >
                  {link.label}
                  {link.count > 0 && <span className="rounded-full bg-rose-500 px-2 text-xs font-bold text-white">{link.count}</span>}
                </Link>
              ))}
            {isCoach && (
              <button
                onClick={() => {
                  setMobileMenuOpen(false);
                  setIsExerciseModalOpen(true);
                }}
                className="w-full text-left px-3 py-2 rounded-md text-base font-bold text-amber-400 hover:bg-slate-800"
              >
                + Đăng Bài Mẫu Mới (HLV)
              </button>
            )}
            {isAuthenticated ? (
              <button
                onClick={() => {
                  logout();
                  setMobileMenuOpen(false);
                }}
                className="w-full text-left px-3 py-2 rounded-md text-base font-medium text-rose-400 hover:bg-slate-800"
              >
                Đăng xuất ({user?.username} - {isCoach ? "HLV" : "Học Viên"})
              </button>
            ) : (
              <Link
                href="/login"
                onClick={() => setMobileMenuOpen(false)}
                className="block px-3 py-2 rounded-md text-base font-medium text-blue-400 hover:bg-slate-800"
              >
                Đăng Nhập / Đăng Ký
              </Link>
            )}
          </div>
        )}
      </nav>

      {/* Modal đăng bài tập mẫu dành cho HLV */}
      {isCoach && (
        <CreateExerciseModal
          isOpen={isExerciseModalOpen}
          onClose={() => setIsExerciseModalOpen(false)}
          onSuccess={() => {
            setIsExerciseModalOpen(false);
            window.location.reload();
          }}
        />
      )}
    </>
  );
};
