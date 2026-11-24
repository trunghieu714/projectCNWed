"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { call, errorMessage } from "../../services/api";
import { useAuth } from "../../context/AuthContext";
import { Avatar, ErrorBox, RoleBadge, Spinner, timeAgo } from "../../components/common/ui";

type Tab = "users" | "reports" | "courses";

export default function AdminPage() {
  const { isAdmin, isLoading } = useAuth();
  const [tab, setTab] = useState<Tab>("users");
  const [stats, setStats] = useState<Record<string, number> | null>(null);
  const [users, setUsers] = useState<any[]>([]);
  const [reports, setReports] = useState<any[]>([]);
  const [courses, setCourses] = useState<any[]>([]);
  const [keyword, setKeyword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({ phonenumber: "", password: "", username: "", role: "HV" });

  const load = useCallback(async () => {
    try {
      setStats(await call("admin/stats"));
      if (tab === "users") setUsers((await call<any>("admin/users", { keyword, index: 0, count: 100 })).users);
      if (tab === "reports") setReports(await call("admin/reports", { index: 0, count: 100 }));
      if (tab === "courses") setCourses(await call("admin/courses"));
    } catch (e) {
      setError(errorMessage(e));
    }
  }, [tab, keyword]);

  useEffect(() => { if (isAdmin) load(); }, [isAdmin, load]);

  const act = async (name: string, params: Record<string, any>) => {
    setError(null);
    try {
      await call(name, params);
      load();
    } catch (e) {
      setError(errorMessage(e));
    }
  };

  if (isLoading) return <div className="flex justify-center p-10"><Spinner /></div>;
  if (!isAdmin) return <div className="mx-auto max-w-xl p-4"><ErrorBox message="Chỉ quản trị viên mới truy cập được trang này." /></div>;

  return (
    <div className="mx-auto max-w-6xl space-y-4 px-2 py-4">
      <h1 className="text-2xl font-bold">Trang quản trị</h1>
      {stats && (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {[["users", "Người dùng"], ["teachers", "Giáo viên"], ["students", "Học viên"], ["posts", "Bài viết"],
            ["courses", "Khóa học"], ["submissions", "Bài nộp"], ["reports", "Báo cáo"], ["avg_score", "Điểm TB"]].map(([k, label]) => (
            <div key={k} className="card p-3"><div className="text-sm text-ui-textSecondary">{label}</div><div className="text-2xl font-bold">{stats[k]}</div></div>
          ))}
        </div>
      )}
      <div className="flex gap-2">
        {(["users", "reports", "courses"] as Tab[]).map((t) => (
          <button key={t} onClick={() => setTab(t)} className={tab === t ? "btn-primary" : "btn-secondary"}>
            {{ users: "Người dùng", reports: "Báo cáo vi phạm", courses: "Khóa học" }[t]}
          </button>
        ))}
      </div>
      {error && <ErrorBox message={error} />}

      {tab === "users" && (
        <div className="card space-y-3 p-3">
          <form onSubmit={(e) => { e.preventDefault(); act("admin/create_user", form); }} className="grid gap-2 sm:grid-cols-5">
            <input className="input" placeholder="SĐT" value={form.phonenumber} onChange={(e) => setForm({ ...form, phonenumber: e.target.value })} />
            <input className="input" placeholder="Mật khẩu" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
            <input className="input" placeholder="Tên người dùng" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} />
            <select className="input" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}><option value="HV">Học viên</option><option value="GV">Giáo viên</option></select>
            <button className="btn-green">Thêm người dùng</button>
          </form>
          <input className="input" placeholder="Tìm theo tên, SĐT..." value={keyword} onChange={(e) => setKeyword(e.target.value)} />
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="text-left text-ui-textSecondary"><th className="p-2">Người dùng</th><th>SĐT</th><th>Vai trò</th><th>Trạng thái</th><th /></tr></thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id} className="border-t border-ui-divider">
                    <td className="p-2"><Link href={`/profile/${u.id}`} className="flex items-center gap-2"><Avatar src={u.avatar} name={u.name} size={32} /> {u.name}</Link></td>
                    <td>{u.phonenumber}</td>
                    <td>
                      <select className="rounded border border-ui-border p-1" value={u.role} onChange={(e) => act("admin/update_user", { user_id: u.id, role: e.target.value })}>
                        <option value="student">Học viên</option><option value="coach">Giáo viên</option><option value="admin">Quản trị</option>
                      </select>
                    </td>
                    <td>{u.is_active ? "Hoạt động" : <span className="text-ui-red">Đã khóa</span>}</td>
                    <td className="text-right">
                      <button className="btn-secondary" onClick={() => act("admin/update_user", { user_id: u.id, is_active: u.is_active ? 0 : 1 })}>{u.is_active ? "Khóa" : "Mở khóa"}</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === "reports" && (
        <div className="space-y-2">
          {reports.length === 0 && <div className="card p-6 text-center text-ui-textSecondary">Không có báo cáo nào.</div>}
          {reports.map((r) => (
            <div key={r.id} className="card p-3">
              <div className="text-sm text-ui-textSecondary">{r.reporter?.name} báo cáo · {timeAgo(r.created)}</div>
              <div className="font-semibold">{r.subject}</div>
              {r.details && <p className="text-sm">{r.details}</p>}
              {r.post && (
                <Link href={`/posts/${r.post_id}`} className="mt-2 block rounded bg-ui-bg p-2 text-sm">
                  <span className="font-semibold">{r.post.author?.name}</span> <RoleBadge label={r.post.author?.role_label} />: {r.post.described?.slice(0, 200)}
                </Link>
              )}
              <div className="mt-2 flex gap-2">
                {r.post && <button className="btn-primary bg-ui-red hover:bg-ui-red" onClick={() => confirm("Xóa bài viết bị báo cáo?") && act("admin/delete_post", { id: r.post_id })}>Xóa bài viết</button>}
                <button className="btn-secondary" onClick={() => act("admin/delete_report", { id: r.id })}>Bỏ qua báo cáo</button>
              </div>
            </div>
          ))}
        </div>
      )}

      {tab === "courses" && (
        <div className="card divide-y divide-ui-divider">
          {courses.map((c) => (
            <div key={c.id} className="flex flex-wrap items-center gap-2 p-3">
              <Avatar src={c.teacher?.avatar} name={c.teacher?.name} size={36} />
              <input className="input max-w-xs" defaultValue={c.title} onBlur={(e) => e.target.value !== c.title && act("admin/update_course", { course_id: c.id, title: e.target.value })} />
              <span className="text-sm text-ui-textSecondary">GV {c.teacher?.name}</span>
              <label className="ml-auto text-sm">Tối đa
                <input type="number" min={1} max={500} defaultValue={c.max_students} className="ml-1 w-20 rounded border border-ui-border p-1"
                  onBlur={(e) => Number(e.target.value) !== c.max_students && act("admin/update_course", { course_id: c.id, max_students: e.target.value })} /> HV
              </label>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
