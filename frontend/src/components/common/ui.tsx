"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { AlertCircle, Loader2, WifiOff, X } from "lucide-react";
import { mediaUrl } from "../../services/api";
import { MESSAGES } from "../../lib/validation";

export function Avatar({ src, name, size = 40, href }: { src?: string | null; name?: string; size?: number; href?: string }) {
  const initial = (name || "?").trim().charAt(0).toUpperCase();
  const img = src ? (
    // eslint-disable-next-line @next/next/no-img-element
    <img src={mediaUrl(src)} alt={name || "avatar"} className="rounded-full object-cover" style={{ width: size, height: size }} />
  ) : (
    <div
      className="flex items-center justify-center rounded-full bg-ui-blue font-semibold text-white"
      style={{ width: size, height: size, fontSize: size * 0.42 }}
    >
      {initial}
    </div>
  );
  return href ? <Link href={href} className="shrink-0">{img}</Link> : <div className="shrink-0">{img}</div>;
}

export function Spinner({ className = "" }: { className?: string }) {
  return <Loader2 className={`h-5 w-5 animate-spin text-ui-blue ${className}`} />;
}

export function LoadingCard() {
  return (
    <div className="card p-4">
      <div className="flex animate-pulse items-center gap-3">
        <div className="h-10 w-10 rounded-full bg-ui-divider" />
        <div className="flex-1 space-y-2">
          <div className="h-3 w-1/3 rounded bg-ui-divider" />
          <div className="h-3 w-1/5 rounded bg-ui-divider" />
        </div>
      </div>
      <div className="mt-4 h-48 animate-pulse rounded bg-ui-divider" />
    </div>
  );
}

export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex items-start gap-2 rounded-md border border-ui-red/30 bg-ui-red/5 p-3 text-sm text-ui-red">
      <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
      <span className="flex-1">{message}</span>
      {onRetry && (
        <button onClick={onRetry} className="font-semibold underline">
          Thử lại
        </button>
      )}
    </div>
  );
}

export function Modal({ open, onClose, title, children, wide = false }: {
  open: boolean; onClose: () => void; title: string; children: React.ReactNode; wide?: boolean;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/80 backdrop-blur-sm p-0 animate-fade-in sm:items-center sm:p-4" onClick={onClose}>
      <div
        className={`card max-h-[92vh] w-full overflow-y-auto shadow-pop animate-slide-up sm:animate-fade-in ${wide ? "max-w-3xl" : "max-w-lg"}`}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-label={title}
      >
        <div className="sticky top-0 z-10 flex items-center justify-center border-b border-ui-divider bg-ui-card px-4 py-3">
          <h2 className="text-lg font-bold">{title}</h2>
          <button onClick={onClose} className="absolute right-3 rounded-full bg-ui-divider p-1.5 hover:bg-ui-border" aria-label="Đóng">
            <X className="h-5 w-5 text-ui-textSecondary" />
          </button>
        </div>
        <div className="p-4">{children}</div>
      </div>
    </div>
  );
}

/** Báo mất kết nối càng sớm càng tốt (Slide 34). */
export function NetworkBanner() {
  const [online, setOnline] = useState(true);
  useEffect(() => {
    const update = () => setOnline(navigator.onLine);
    update();
    window.addEventListener("online", update);
    window.addEventListener("offline", update);
    return () => {
      window.removeEventListener("online", update);
      window.removeEventListener("offline", update);
    };
  }, []);
  if (online) return null;
  return (
    <div className="fixed bottom-4 left-1/2 z-50 flex -translate-x-1/2 items-center gap-2 rounded-lg bg-ui-text px-4 py-3 text-sm text-white shadow-pop">
      <WifiOff className="h-4 w-4" /> {MESSAGES.network}
    </div>
  );
}

export function timeAgo(iso?: string | null): string {
  if (!iso) return "";
  const d = new Date(iso.endsWith("Z") || iso.includes("+") ? iso : iso + "Z");
  const s = Math.max(0, (Date.now() - d.getTime()) / 1000);
  if (s < 60) return "Vừa xong";
  if (s < 3600) return `${Math.floor(s / 60)} phút`;
  if (s < 86400) return `${Math.floor(s / 3600)} giờ`;
  if (s < 7 * 86400) return `${Math.floor(s / 86400)} ngày`;
  return d.toLocaleDateString("vi-VN");
}

export function RoleBadge({ label }: { label?: string }) {
  if (!label) return null;
  const style = label === "GV" ? "bg-ui-orange/20 text-[#8a5a00]" : label === "BOT" ? "bg-ui-blueLight text-ui-blue" : "bg-ui-divider text-ui-textSecondary";
  return <span className={`rounded px-1.5 py-0.5 text-[11px] font-semibold ${style}`}>{label === "GV" ? "Giáo viên" : label === "HV" ? "Học viên" : label}</span>;
}

/** Báo cáo HTML chi tiết lỗi do server sinh, hiển thị trong iframe sandbox (không chạy script). */
export function ReportFrame({ html, url }: { html?: string | null; url?: string | null }) {
  if (html) return <iframe title="Chi tiết lỗi" sandbox="allow-same-origin" srcDoc={html} className="h-[70vh] w-full rounded-xl border border-slate-800 bg-white" />;
  if (url) return <iframe title="Chi tiết lỗi" sandbox="allow-same-origin" src={mediaUrl(url)} className="h-[70vh] w-full rounded-xl border border-slate-800 bg-white" />;
  return null;
}
