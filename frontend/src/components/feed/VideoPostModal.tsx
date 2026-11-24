"use client";

import React, { useEffect, useState } from "react";
import { ArrowLeftRight, Film, Trash2, Upload } from "lucide-react";
import { call, errorMessage, mediaUrl } from "../../services/api";
import { countWords, MAX_WORDS, videoError } from "../../lib/validation";
import { useAuth } from "../../context/AuthContext";
import { SpecPost } from "../../types/spec";
import { Avatar, ErrorBox, Modal, Spinner } from "../common/ui";

type Mode = "create" | "submit" | "edit";

interface Props {
  open: boolean;
  onClose: () => void;
  onDone: (postId: number) => void;
  mode?: Mode;
  /** submit: bài tập (bài viết của GV) mà HV nộp; edit: bài đang sửa */
  post?: SpecPost | null;
}

function VideoSlot({ label, file, currentUrl, onPick, onClear }: {
  label: string; file: File | null; currentUrl?: string | null; onPick: (f: File) => void; onClear: () => void;
}) {
  const preview = file ? URL.createObjectURL(file) : currentUrl ? mediaUrl(currentUrl) : null;
  useEffect(() => () => { if (file && preview) URL.revokeObjectURL(preview); }, [file, preview]);
  return (
    <div className="rounded-lg border border-ui-divider p-2">
      <div className="mb-1 flex items-center justify-between text-sm font-semibold">
        <span>{label}</span>
        {file && <button type="button" onClick={onClear} className="text-ui-textSecondary hover:text-ui-red" aria-label="Bỏ video"><Trash2 className="h-4 w-4" /></button>}
      </div>
      {preview ? (
        <video src={preview} className="aspect-video w-full rounded bg-black" controls muted />
      ) : (
        <div className="flex aspect-video items-center justify-center rounded bg-ui-bg text-ui-textMuted"><Film className="h-8 w-8" /></div>
      )}
      <label className="btn-secondary mt-2 w-full cursor-pointer text-xs">
        <Upload className="h-4 w-4" /> {file || currentUrl ? "Chọn video khác" : "Chọn video từ máy"}
        <input type="file" accept="video/*" className="hidden" onChange={(e) => e.target.files?.[0] && onPick(e.target.files[0])} />
      </label>
    </div>
  );
}

export function VideoPostModal({ open, onClose, onDone, mode = "create", post }: Props) {
  const { user, isCoach } = useAuth();
  const [described, setDescribed] = useState("");
  const [left, setLeft] = useState<File | null>(null);
  const [right, setRight] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [checking, setChecking] = useState(false);

  useEffect(() => {
    if (!open) return;
    setError(null);
    setLeft(null);
    setRight(null);
    setDescribed(mode === "edit" && post ? post.described.replace(/^(#(course|exercise)_\d+\s*)+/, "") : "");
  }, [open, mode, post]);

  const pick = async (side: "L" | "R", f: File) => {
    setChecking(true);
    const err = await videoError(f);
    setChecking(false);
    if (err) return setError(err);
    setError(null);
    side === "L" ? setLeft(f) : setRight(f);
  };

  const words = countWords(described);
  const title = mode === "submit" ? "Nộp bài tập" : mode === "edit" ? "Chỉnh sửa bài viết" : "Tạo bài viết";

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (words > MAX_WORDS) return setError(`Nội dung vượt quá ${MAX_WORDS} từ.`);
    if (mode === "submit" && !left && !right) return setError("Bài nộp cần ít nhất 01 video (tối đa 02 góc quay).");
    if (mode === "create" && !described.trim() && !left && !right) return setError("Hãy viết nội dung hoặc chọn video.");
    setBusy(true);
    setError(null);
    try {
      if (mode === "edit" && post) {
        // Chọn file mới cho một bên = thay video bên đó (hoặc bổ sung nếu bên đó đang trống)
        const indices = `${left ? "L" : ""}${right ? "R" : ""}`;
        await call("edit_post", { id: post.id, described, video_indices: indices || undefined, left_video: left, right_video: right });
        onDone(post.id);
      } else {
        const data = await call<any>("add_post", {
          described,
          left_video: left,
          right_video: right,
          exercise_id: mode === "submit" ? post?.id : undefined,
          course_id: mode === "submit" ? post?.author.id : undefined,
          device_master: "web",
          device_slave: left && right ? "web-2" : undefined,
        });
        onDone(data.id);
      }
      onClose();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal open={open} onClose={busy ? () => {} : onClose} title={title} wide>
      <form onSubmit={submit} className="space-y-3">
        <div className="flex items-center gap-2">
          <Avatar src={user?.avatar_url} name={user?.username} />
          <div>
            <div className="font-semibold">{user?.full_name || user?.username}</div>
            <div className="text-xs text-ui-textSecondary">🌐 Công khai{mode === "submit" && post ? ` · Bài tập #${post.id} của ${post.author.name}` : ""}</div>
          </div>
        </div>
        {mode === "create" && isCoach && (
          <p className="rounded-md bg-ui-blueLight p-2 text-xs text-ui-blue">
            Bài đăng có video của giáo viên là <b>video chuẩn</b> (bài tập) dùng làm đáp án chấm điểm cho học viên.
          </p>
        )}
        <textarea
          value={described}
          onChange={(e) => setDescribed(e.target.value)}
          rows={4}
          className="w-full resize-none text-lg outline-none placeholder-ui-textMuted"
          placeholder={mode === "submit" ? "Ghi chú cho bài nộp của bạn..." : `${user?.username || "Bạn"} ơi, bạn đang tập động tác gì?`}
        />
        <div className={`text-right text-xs ${words > MAX_WORDS ? "text-ui-red" : "text-ui-textMuted"}`}>{words}/{MAX_WORDS} từ</div>

        <div className="grid grid-cols-1 gap-2 sm:grid-cols-[1fr_auto_1fr] sm:items-center">
          <VideoSlot label="Góc quay trái" file={left} currentUrl={mode === "edit" ? post?.video_left_url : null}
            onPick={(f) => pick("L", f)} onClear={() => setLeft(null)} />
          <button type="button" title="Đổi bên trái / phải" className="btn-ghost mx-auto"
            onClick={() => { setLeft(right); setRight(left); }} disabled={mode === "edit"}>
            <ArrowLeftRight className="h-5 w-5" />
          </button>
          <VideoSlot label="Góc quay phải" file={right} currentUrl={mode === "edit" ? post?.video_right_url : null}
            onPick={(f) => pick("R", f)} onClear={() => setRight(null)} />
        </div>
        <p className="text-xs text-ui-textSecondary">
          Tối đa 02 video (2 góc nhìn quay cùng lúc), mỗi video tối thiểu 10 giây. Hai video sẽ được ghép thành một.
        </p>
        {checking && <p className="flex items-center gap-2 text-sm text-ui-textSecondary"><Spinner /> Đang kiểm tra video...</p>}
        {error && <ErrorBox message={error} />}
        <button className="btn-primary w-full py-2.5" disabled={busy || checking}>
          {busy ? <><Spinner className="text-white" /> Đang tải lên...</> : mode === "submit" ? "Nộp bài" : mode === "edit" ? "Lưu" : "Đăng"}
        </button>
      </form>
    </Modal>
  );
}
