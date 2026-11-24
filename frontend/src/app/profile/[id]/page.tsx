"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Ban, Camera, MessageCircle, Pencil } from "lucide-react";
import { call, errorMessage, mediaUrl } from "../../../services/api";
import { useAuth } from "../../../context/AuthContext";
import { usernameError } from "../../../lib/validation";
import { UserInfo } from "../../../types/spec";
import { Avatar, ErrorBox, Modal, RoleBadge, Spinner } from "../../../components/common/ui";
import { Feed } from "../../../components/feed/Feed";

export default function ProfilePage() {
  const { id } = useParams<{ id: string }>();
  const { session, refreshUser } = useAuth();
  const [info, setInfo] = useState<UserInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({ username: "", full_name: "", height: "", description: "" });
  const [avatar, setAvatar] = useState<File | null>(null);
  const [cover, setCover] = useState<File | null>(null);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const isMe = session?.user_id === Number(id);

  const load = () =>
    call<UserInfo>("get_user_info", { user_id: id })
      .then((u) => { setInfo(u); setError(null); })
      .catch((e) => setError(errorMessage(e)));

  useEffect(() => { load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [id]);

  const openEdit = () => {
    if (!info) return;
    setForm({ username: info.username, full_name: info.full_name || "", height: info.height ? String(info.height) : "", description: info.description || "" });
    setAvatar(null);
    setCover(null);
    setFormError(null);
    setEditing(true);
  };

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    const err = usernameError(form.username, info?.phonenumber);
    if (err) return setFormError(err);
    setSaving(true);
    try {
      await call("set_user_info", {
        username: form.username !== info?.username ? form.username.trim() : undefined,
        full_name: form.full_name, height: form.height || undefined, description: form.description, avatar, cover_image: cover,
      });
      setEditing(false);
      await load();
      await refreshUser();
    } catch (err2) {
      setFormError(errorMessage(err2));
    } finally {
      setSaving(false);
    }
  };

  const toggleBlock = async () => {
    if (!info) return;
    if (!info.is_blocked && !confirm(`Chặn ${info.username}?`)) return;
    try {
      await call("set_block", { user_id: info.id, type: info.is_blocked ? 1 : 0 });
      await load();
    } catch (e) {
      setError(errorMessage(e));
    }
  };

  if (error && !info) return <div className="mx-auto max-w-[680px] p-4"><ErrorBox message={error} /></div>;
  if (!info) return <div className="flex justify-center p-10"><Spinner /></div>;

  return (
    <div>
      <div className="border-b border-slate-800 bg-slate-900/80">
        <div className="mx-auto max-w-[940px]">
          <div className="relative h-48 rounded-b-lg bg-gradient-to-b from-ui-divider to-ui-border sm:h-72"
            style={info.cover_image ? { backgroundImage: `url(${mediaUrl(info.cover_image)})`, backgroundSize: "cover", backgroundPosition: "center" } : undefined} />
          <div className="flex flex-col items-center gap-3 px-4 pb-4 sm:flex-row sm:items-end">
            <div className="-mt-16 rounded-full border-4 border-slate-950"><Avatar src={info.avatar} name={info.username} size={150} /></div>
            <div className="flex-1 text-center sm:text-left">
              <h1 className="text-3xl font-bold">{info.full_name || info.username}</h1>
              <div className="flex flex-wrap items-center justify-center gap-2 text-ui-textSecondary sm:justify-start">
                @{info.username} <RoleBadge label={info.role_label} />
                <span>· {info.listing} bài viết</span>
                <span>· {info.role_label === "GV" ? `${info.followed} học viên` : `${info.followed} khóa học`}</span>
                {info.height ? <span>· {info.height} cm</span> : null}
              </div>
              {info.description && <p className="mt-1">{info.description}</p>}
            </div>
            <div className="flex gap-2">
              {isMe ? (
                <button onClick={openEdit} className="btn-secondary"><Pencil className="h-4 w-4" /> Chỉnh sửa trang cá nhân</button>
              ) : (
                <>
                  {!info.is_blocked && <Link href={`/messages?partner=${info.id}`} className="btn-primary"><MessageCircle className="h-4 w-4" /> Nhắn tin</Link>}
                  <button onClick={toggleBlock} className="btn-secondary"><Ban className="h-4 w-4" /> {info.is_blocked ? "Bỏ chặn" : "Chặn"}</button>
                </>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-[680px] px-2 py-4">
        {error && <div className="mb-3"><ErrorBox message={error} /></div>}
        {info.is_blocked ? (
          <div className="card p-6 text-center text-ui-textSecondary">Bạn đã chặn người dùng này.</div>
        ) : (
          <Feed key={info.id} filter={{ user_id: info.id }} emptyText="Chưa có bài viết nào." />
        )}
      </div>

      <Modal open={editing} onClose={() => setEditing(false)} title="Chỉnh sửa trang cá nhân">
        <form onSubmit={save} className="space-y-3">
          <label className="block text-sm font-semibold">Tên người dùng<input className="input mt-1" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} /></label>
          <label className="block text-sm font-semibold">Họ tên<input className="input mt-1" value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} /></label>
          <label className="block text-sm font-semibold">Chiều cao (cm)<input className="input mt-1" inputMode="decimal" value={form.height} onChange={(e) => setForm({ ...form, height: e.target.value })} /></label>
          <label className="block text-sm font-semibold">Giới thiệu<textarea className="input mt-1" rows={3} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></label>
          <div className="grid grid-cols-2 gap-2 text-sm">
            <label className="btn-secondary cursor-pointer"><Camera className="h-4 w-4" /> {avatar ? avatar.name : "Ảnh đại diện"}<input type="file" accept="image/*" className="hidden" onChange={(e) => setAvatar(e.target.files?.[0] || null)} /></label>
            <label className="btn-secondary cursor-pointer"><Camera className="h-4 w-4" /> {cover ? cover.name : "Ảnh bìa"}<input type="file" accept="image/*" className="hidden" onChange={(e) => setCover(e.target.files?.[0] || null)} /></label>
          </div>
          {formError && <ErrorBox message={formError} />}
          <button className="btn-primary w-full" disabled={saving}>{saving ? <Spinner className="text-white" /> : "Lưu"}</button>
        </form>
      </Modal>
    </div>
  );
}
