"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Award, Bell, GraduationCap, Heart, LogIn, MessageCircle, MessageSquare, Upload } from "lucide-react";
import { call, errorMessage } from "../../services/api";
import { NotificationItem } from "../../types/spec";
import { Avatar, ErrorBox, Spinner, timeAgo } from "../../components/common/ui";

const ICONS: Record<string, React.ElementType> = {
  like: Heart, comment: MessageSquare, message: MessageCircle, new_post: Upload, submission: Upload,
  enrollment_request: GraduationCap, enrollment_result: GraduationCap, score: Award, login_other_device: LogIn,
};

function target(n: NotificationItem): string | null {
  if (["like", "comment", "new_post", "submission", "score"].includes(n.type) && n.object_id) return `/posts/${n.object_id}`;
  if (n.type === "message" && n.actor) return `/messages?partner=${n.actor.id}`;
  if (n.type.startsWith("enrollment")) return "/courses";
  if (n.type === "login_other_device") return "/settings";
  return null;
}

export default function NotificationsPage() {
  const router = useRouter();
  const [items, setItems] = useState<NotificationItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () =>
    call<{ notifications: NotificationItem[] }>("get_notification", { index: 0, count: 50 })
      .then((d) => setItems(d.notifications))
      .catch((e) => { setItems([]); setError(errorMessage(e)); });
  useEffect(() => { load(); }, []);

  const open = async (n: NotificationItem) => {
    if (!n.read) await call("set_read_notification", { notification_id: n.id }).catch(() => {});
    const url = target(n);
    if (url) router.push(url);
    else load();
  };

  return (
    <div className="mx-auto max-w-[680px] px-2 py-4">
      <div className="card p-2">
        <div className="flex items-center justify-between p-2">
          <h1 className="text-2xl font-bold">Thông báo</h1>
          <button className="text-sm font-semibold text-ui-blue" onClick={() => call("set_read_notification", { all: 1 }).then(load)}>Đánh dấu tất cả đã đọc</button>
        </div>
        {error && <ErrorBox message={error} />}
        {items === null && <div className="p-4"><Spinner /></div>}
        {items?.length === 0 && <p className="p-4 text-center text-ui-textSecondary">Chưa có thông báo nào.</p>}
        {items?.map((n) => {
          const Icon = ICONS[n.type] || Bell;
          return (
            <button key={n.id} onClick={() => open(n)} className={`flex w-full items-center gap-3 rounded-lg p-2 text-left hover:bg-ui-hover ${n.read ? "" : "bg-ui-blueLight/50"}`}>
              <div className="relative">
                <Avatar src={n.actor?.avatar} name={n.actor?.name || n.title} size={52} />
                <span className="absolute -bottom-1 -right-1 rounded-full bg-ui-blue p-1 text-white"><Icon className="h-3.5 w-3.5" /></span>
              </div>
              <div className="min-w-0 flex-1">
                <div className="font-semibold">{n.title}</div>
                <div className="text-sm">{n.body}</div>
                <div className={`text-xs ${n.read ? "text-ui-textSecondary" : "font-semibold text-ui-blue"}`}>{timeAgo(n.created)}</div>
              </div>
              {!n.read && <span className="h-3 w-3 rounded-full bg-ui-blue" />}
            </button>
          );
        })}
      </div>
    </div>
  );
}
