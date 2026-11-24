"use client";

import React, { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Clock, Search, X } from "lucide-react";
import { call, errorMessage } from "../../services/api";
import { useAuth } from "../../context/AuthContext";
import { SpecPost } from "../../types/spec";
import { ErrorBox, LoadingCard } from "../../components/common/ui";
import { PostCard } from "../../components/feed/PostCard";

function SearchInner() {
  const router = useRouter();
  const params = useSearchParams();
  const q = params.get("q") || "";
  const { isAuthenticated } = useAuth();
  const [keyword, setKeyword] = useState(q);
  const [results, setResults] = useState<SpecPost[] | null>(null);
  const [history, setHistory] = useState<{ id: number; keyword: string }[]>([]);
  const [error, setError] = useState<string | null>(null);

  const loadHistory = () => isAuthenticated && call<any[]>("get_saved_search").then(setHistory).catch(() => {});

  useEffect(() => {
    setKeyword(q);
    if (!q) {
      setResults(null);
      loadHistory();
      return;
    }
    setResults(null);
    setError(null);
    call<SpecPost[]>("search", { keyword: q, index: 0, count: 50 })
      .then(setResults)
      .catch((e) => { setResults([]); setError(errorMessage(e)); });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q, isAuthenticated]);

  const go = (e: React.FormEvent) => {
    e.preventDefault();
    if (keyword.trim()) router.push(`/search?q=${encodeURIComponent(keyword.trim())}`);
  };

  return (
    <div className="mx-auto max-w-[680px] space-y-4 px-2 py-4">
      <form onSubmit={go} className="card flex items-center gap-2 p-3">
        <Search className="h-5 w-5 text-ui-textSecondary" />
        <input value={keyword} onChange={(e) => setKeyword(e.target.value)} autoFocus
          placeholder="Tìm bài viết (không phân biệt thứ tự từ, có dấu hay không dấu)" className="flex-1 outline-none" />
        <button className="btn-primary">Tìm</button>
      </form>
      {!q && history.length > 0 && (
        <div className="card p-3">
          <div className="mb-2 flex items-center justify-between">
            <h2 className="font-semibold">Tìm kiếm gần đây</h2>
            <button className="text-sm text-ui-blue" onClick={() => call("del_saved_search", { all: 1 }).then(() => setHistory([]))}>Xóa tất cả</button>
          </div>
          {history.map((h) => (
            <div key={h.id} className="flex items-center justify-between rounded p-2 hover:bg-ui-hover">
              <button className="flex items-center gap-2" onClick={() => router.push(`/search?q=${encodeURIComponent(h.keyword)}`)}>
                <Clock className="h-4 w-4 text-ui-textSecondary" /> {h.keyword}
              </button>
              <button aria-label="Xóa" onClick={() => call("del_saved_search", { search_id: h.id }).then(() => setHistory((x) => x.filter((i) => i.id !== h.id)))}>
                <X className="h-4 w-4 text-ui-textSecondary" />
              </button>
            </div>
          ))}
        </div>
      )}
      {error && <ErrorBox message={error} />}
      {q && results === null && <LoadingCard />}
      {results?.length === 0 && !error && <div className="card p-6 text-center text-ui-textSecondary">Không tìm thấy bài viết nào cho “{q}”.</div>}
      {results?.map((p) => <PostCard key={p.id} post={p} />)}
    </div>
  );
}

export default function SearchPage() {
  return <Suspense fallback={null}><SearchInner /></Suspense>;
}
