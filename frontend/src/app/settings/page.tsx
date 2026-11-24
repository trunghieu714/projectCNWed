"use client";

import React, { useEffect, useState } from "react";
import { call, errorMessage } from "../../services/api";
import { passwordError } from "../../lib/validation";
import { useAuth } from "../../context/AuthContext";
import { UserBrief } from "../../types/spec";
import { Avatar, ErrorBox, Spinner } from "../../components/common/ui";

interface PushSettings {
  notification_on: boolean;
  sound_mode: number;
  like_comment: boolean;
  new_post: boolean;
  message: boolean;
  enrollment: boolean;
  score: boolean;
}

const TOGGLES: [keyof PushSettings, string][] = [
  ["like_comment", "Lượt thích & bình luận"],
  ["new_post", "Bài viết / bài nộp mới"],
  ["message", "Tin nhắn"],
  ["enrollment", "Đăng ký khóa học"],
  ["score", "Kết quả chấm điểm"],
];

export default function SettingsPage() {
  const { user } = useAuth();
  const [push, setPush] = useState<PushSettings | null>(null);
  const [blocks, setBlocks] = useState<UserBrief[]>([]);
  const [pw, setPw] = useState({ old: "", next: "" });
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadBlocks = () => call<any>("get_list_blocks", { index: 0, count: 100 }).then((d) => setBlocks(d.users)).catch(() => {});
  useEffect(() => {
    call<PushSettings>("get_push_settings").then(setPush).catch((e) => setError(errorMessage(e)));
    loadBlocks();
  }, []);

  const update = async (patch: Partial<PushSettings>) => {
    try {
      setPush(await call<PushSettings>("set_push_settings", patch as any));
    } catch (e) {
      setError(errorMessage(e));
    }
  };

  const preview = (mode: number) => {
    if (mode === 2 && "speechSynthesis" in window) window.speechSynthesis.speak(new SpeechSynthesisUtterance("Bạn có thông báo mới"));
    if (mode === 1) {
      const ctx = new AudioContext();
      const o = ctx.createOscillator();
      o.frequency.value = 880;
      o.connect(ctx.destination);
      o.start();
      o.stop(ctx.currentTime + 0.15);
    }
  };

  const changePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setMsg(null);
    const err = passwordError(pw.next, user?.phonenumber);
    if (err) return setError(err);
    try {
      await call("change_password", { password: pw.old, new_password: pw.next });
      setPw({ old: "", next: "" });
      setError(null);
      setMsg("Đổi mật khẩu thành công.");
    } catch (e2) {
      setError(errorMessage(e2));
    }
  };

  return (
    <div className="mx-auto max-w-[680px] space-y-4 px-2 py-4">
      <h1 className="text-2xl font-bold">Cài đặt</h1>
      {error && <ErrorBox message={error} />}
      {msg && <p className="rounded-md bg-ui-blueLight p-3 text-sm text-ui-blue">{msg}</p>}

      <section className="card space-y-3 p-4">
        <h2 className="text-lg font-bold">Thông báo đẩy</h2>
        {!push ? <Spinner /> : (
          <>
            <label className="flex items-center justify-between">
              <span>Nhận thông báo</span>
              <input type="checkbox" checked={push.notification_on} onChange={(e) => update({ notification_on: e.target.checked })} />
            </label>
            <div>
              <div className="mb-1 text-sm font-semibold">Âm thanh thông báo</div>
              {[[0, "Tắt âm thanh"], [1, "Âm mặc định (tiếng kêu)"], [2, "Âm có tiếng nói"]].map(([mode, label]) => (
                <label key={mode} className="flex items-center gap-2 py-1">
                  <input type="radio" disabled={!push.notification_on} checked={push.sound_mode === mode} onChange={() => { update({ sound_mode: mode as number }); preview(mode as number); }} />
                  {label}
                </label>
              ))}
            </div>
            <div className="border-t border-ui-divider pt-2">
              {TOGGLES.map(([key, label]) => (
                <label key={key} className="flex items-center justify-between py-1">
                  <span>{label}</span>
                  <input type="checkbox" disabled={!push.notification_on} checked={push[key] as boolean} onChange={(e) => update({ [key]: e.target.checked })} />
                </label>
              ))}
            </div>
          </>
        )}
      </section>

      <form onSubmit={changePassword} className="card space-y-2 p-4">
        <h2 className="text-lg font-bold">Đổi mật khẩu</h2>
        <input className="input" type="password" placeholder="Mật khẩu hiện tại" value={pw.old} onChange={(e) => setPw({ ...pw, old: e.target.value })} />
        <input className="input" type="password" placeholder="Mật khẩu mới" value={pw.next} onChange={(e) => setPw({ ...pw, next: e.target.value })} />
        <button className="btn-primary">Đổi mật khẩu</button>
      </form>

      <section className="card p-4">
        <h2 className="mb-2 text-lg font-bold">Danh sách chặn ({blocks.length})</h2>
        {blocks.length === 0 && <p className="text-sm text-ui-textSecondary">Bạn chưa chặn ai.</p>}
        {blocks.map((b) => (
          <div key={b.id!} className="flex items-center gap-3 py-2">
            <Avatar src={b.avatar} name={b.name} size={36} />
            <span className="flex-1 font-semibold">{b.name}</span>
            <button className="btn-secondary" onClick={() => call("set_block", { user_id: b.id!, type: 1 }).then(loadBlocks).catch((e) => setError(errorMessage(e)))}>Bỏ chặn</button>
          </div>
        ))}
      </section>
      <p className="text-center text-xs text-ui-textMuted">Theo quy định, tài khoản không thể tự xóa.</p>
    </div>
  );
}
