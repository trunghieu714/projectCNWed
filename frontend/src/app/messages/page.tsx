"use client";

import React, { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Send, Trash2 } from "lucide-react";
import { call, errorMessage } from "../../services/api";
import { useAuth } from "../../context/AuthContext";
import { ChatMessage, ConversationItem, UserBrief } from "../../types/spec";
import { Avatar, ErrorBox, Spinner, timeAgo } from "../../components/common/ui";
import { emojify } from "../../lib/emoticons";

function MessagesInner() {
  const router = useRouter();
  const params = useSearchParams();
  const partnerId = Number(params.get("partner")) || null;
  const { session } = useAuth();
  const [convs, setConvs] = useState<ConversationItem[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [partner, setPartner] = useState<UserBrief | null>(null);
  const [blocked, setBlocked] = useState(false);
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const bottom = useRef<HTMLDivElement>(null);

  const loadConvs = useCallback(() => call<any>("get_list_conversation", { index: 0, count: 50 }).then((d) => setConvs(d.conversations)).catch(() => {}), []);

  const loadMessages = useCallback(async (silent = false) => {
    if (!partnerId) return;
    if (!silent) setLoading(true);
    try {
      const d = await call<any>("get_conversation", { partner_id: partnerId, index: 0, count: 100 });
      setMessages(d.conversation);
      setPartner(d.partner);
      setBlocked(d.is_blocked);
      await call("set_read_message", { partner_id: partnerId });
    } catch (e: any) {
      if (e?.code === "9994") {
        setMessages([]);
        const u = await call<any>("get_user_info", { user_id: partnerId }).catch(() => null);
        if (u) setPartner({ id: u.id, username: u.username, name: u.full_name || u.username, avatar: u.avatar, role: u.role, role_label: u.role_label });
      } else if (!silent) setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }, [partnerId]);

  useEffect(() => { loadConvs(); }, [loadConvs]);
  useEffect(() => { setError(null); loadMessages(); }, [loadMessages]);
  useEffect(() => {
    const t = setInterval(() => { loadConvs(); loadMessages(true); }, 5000);
    return () => clearInterval(t);
  }, [loadConvs, loadMessages]);
  useEffect(() => { bottom.current?.scrollIntoView({ behavior: "smooth" }); }, [messages.length]);

  const send = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!text.trim() || !partnerId) return;
    try {
      const m = await call<ChatMessage>("set_conversation", { partner_id: partnerId, content: text.trim() });
      setMessages((prev) => [...prev, m]);
      setText("");
      loadConvs();
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  const removeMessage = async (id: number) => {
    try {
      await call("delete_message", { message_id: id });
      setMessages((prev) => prev.filter((m) => m.id !== id));
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  const removeConversation = async () => {
    if (!partnerId || !confirm("Xóa cuộc trò chuyện này ở phía bạn?")) return;
    await call("delete_conversation", { partner_id: partnerId }).catch(() => {});
    router.push("/messages");
    loadConvs();
  };

  return (
    <div className="mx-auto grid h-[calc(100vh-56px)] max-w-6xl grid-cols-1 gap-2 p-2 md:grid-cols-[320px_1fr]">
      <aside className={`card overflow-y-auto p-2 ${partnerId ? "hidden md:block" : ""}`}>
        <h1 className="p-2 text-2xl font-bold">Đoạn chat</h1>
        {convs.length === 0 && <p className="p-2 text-sm text-ui-textSecondary">Chưa có cuộc trò chuyện. Vào trang cá nhân của ai đó và bấm “Nhắn tin”.</p>}
        {convs.map((c) => (
          <button key={c.id} onClick={() => router.push(`/messages?partner=${c.partner.id}`)}
            className={`flex w-full items-center gap-3 rounded-lg p-2 text-left hover:bg-ui-hover ${c.partner.id === partnerId ? "bg-ui-blueLight" : ""}`}>
            <Avatar src={c.partner.avatar} name={c.partner.name} size={48} />
            <div className="min-w-0 flex-1">
              <div className="font-semibold">{c.partner.name}</div>
              <div className={`truncate text-sm ${c.unread_count ? "font-bold" : "text-ui-textSecondary"}`}>
                {c.lastmessage.sender_id === session?.user_id ? "Bạn: " : ""}{emojify(c.lastmessage.message)} · {timeAgo(c.lastmessage.created)}
              </div>
            </div>
            {c.unread_count > 0 && <span className="h-3 w-3 rounded-full bg-ui-blue" />}
          </button>
        ))}
      </aside>

      <section className={`card flex flex-col ${partnerId ? "" : "hidden md:flex"}`}>
        {!partnerId ? (
          <div className="m-auto text-ui-textSecondary">Chọn một cuộc trò chuyện</div>
        ) : (
          <>
            <header className="flex items-center gap-2 border-b border-ui-divider p-3">
              <button className="md:hidden" onClick={() => router.push("/messages")}>←</button>
              <Avatar src={partner?.avatar} name={partner?.name} href={`/profile/${partnerId}`} />
              <div className="flex-1 font-semibold">{partner?.name}</div>
              <button onClick={removeConversation} className="btn-ghost" title="Xóa cuộc trò chuyện"><Trash2 className="h-5 w-5" /></button>
            </header>
            <div className="flex-1 space-y-1 overflow-y-auto p-3">
              {loading && <Spinner />}
              {messages.map((m) => {
                const mine = m.sender_id === session?.user_id;
                return (
                  <div key={m.id} className={`group flex items-end gap-2 ${mine ? "justify-end" : ""}`}>
                    {mine && <button onClick={() => removeMessage(m.id)} className="hidden text-ui-textMuted group-hover:block" title="Xóa tin nhắn"><Trash2 className="h-4 w-4" /></button>}
                    <div title={timeAgo(m.created)} className={`max-w-[70%] whitespace-pre-line break-words rounded-2xl px-3 py-2 ${mine ? "bg-ui-blue text-white" : "bg-ui-divider"}`}>{emojify(m.message)}</div>
                  </div>
                );
              })}
              <div ref={bottom} />
            </div>
            {error && <div className="px-3"><ErrorBox message={error} /></div>}
            {blocked ? (
              <p className="p-3 text-center text-sm text-ui-textSecondary">Bạn không thể nhắn tin với người này.</p>
            ) : (
              <form onSubmit={send} className="flex items-center gap-2 p-3">
                <input value={text} onChange={(e) => setText(e.target.value)} placeholder="Aa  (gõ :) <3 để chèn emoticon)" className="h-10 flex-1 rounded-full bg-ui-bg px-4 outline-none" />
                <button disabled={!text.trim()} className="text-ui-blue disabled:opacity-40" aria-label="Gửi"><Send className="h-6 w-6" /></button>
              </form>
            )}
          </>
        )}
      </section>
    </div>
  );
}

export default function MessagesPage() {
  return <Suspense fallback={null}><MessagesInner /></Suspense>;
}
