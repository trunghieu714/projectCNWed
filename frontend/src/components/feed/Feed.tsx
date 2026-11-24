"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { ArrowUp, RefreshCw } from "lucide-react";
import { call, errorMessage } from "../../services/api";
import { PostList, SpecPost } from "../../types/spec";
import { ErrorBox, LoadingCard, Spinner } from "../common/ui";
import { PostCard } from "./PostCard";

const PAGE = 10;
const CACHE_KEY = "feed_cache";

interface Props {
  /** Tham số lọc thêm cho get_list_posts (user_id, only_exercises...) */
  filter?: Record<string, string | number>;
  /** Chỉ cache màn hình trang chủ (Slide 33) */
  cacheHome?: boolean;
  header?: React.ReactNode;
  emptyText?: string;
}

export function Feed({ filter = {}, cacheHome = false, header, emptyText = "Chưa có bài viết nào." }: Props) {
  const [posts, setPosts] = useState<SpecPost[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [newItems, setNewItems] = useState(0);
  const [pull, setPull] = useState(0);
  const lastId = useRef(0);
  const sentinel = useRef<HTMLDivElement>(null);
  const touchStart = useRef<number | null>(null);
  const filterKey = JSON.stringify(filter);

  const load = useCallback(async (index: number) => {
    const data = await call<PostList>("get_list_posts", { index, count: PAGE, ...JSON.parse(filterKey) });
    return data;
  }, [filterKey]);

  const refresh = useCallback(async () => {
    setError(null);
    try {
      const data = await load(0);
      setPosts(data.posts);
      setHasMore(data.posts.length === PAGE);
      lastId.current = data.last_id;
      setNewItems(0);
      if (cacheHome) {
        try { localStorage.setItem(CACHE_KEY, JSON.stringify(data.posts)); } catch {}
      }
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }, [load, cacheHome]);

  useEffect(() => {
    setLoading(true);
    if (cacheHome) {
      // Hiển thị ngay dữ liệu cache, sau đó làm mới từ server
      try {
        const cached = localStorage.getItem(CACHE_KEY);
        if (cached) {
          setPosts(JSON.parse(cached));
          setLoading(false);
        }
      } catch {}
    }
    refresh();
  }, [refresh, cacheHome]);

  const loadMore = useCallback(async () => {
    if (loadingMore || !hasMore || loading) return;
    setLoadingMore(true);
    try {
      const data = await load(posts.length);
      setPosts((prev) => [...prev, ...data.posts.filter((p) => !prev.some((x) => x.id === p.id))]);
      setHasMore(data.posts.length === PAGE);
    } catch (e: any) {
      if (e?.code === "9994") setHasMore(false);
      else setError(errorMessage(e));
    } finally {
      setLoadingMore(false);
    }
  }, [loadingMore, hasMore, loading, load, posts.length]);

  // Pull up to load more: tự tải khi cuộn tới cuối danh sách
  useEffect(() => {
    const el = sentinel.current;
    if (!el) return;
    const obs = new IntersectionObserver((entries) => entries[0].isIntersecting && loadMore(), { rootMargin: "400px" });
    obs.observe(el);
    return () => obs.disconnect();
  }, [loadMore]);

  // Kiểm tra bài mới định kỳ (check_new_item)
  useEffect(() => {
    const t = setInterval(async () => {
      if (!lastId.current) return;
      try {
        const r = await call<{ new_items: number }>("check_new_item", { last_id: lastId.current });
        setNewItems(r.new_items);
      } catch {}
    }, 30000);
    return () => clearInterval(t);
  }, []);

  // Pull down to refresh (màn hình cảm ứng)
  const onTouchStart = (e: React.TouchEvent) => {
    touchStart.current = window.scrollY <= 0 ? e.touches[0].clientY : null;
  };
  const onTouchMove = (e: React.TouchEvent) => {
    if (touchStart.current === null) return;
    setPull(Math.max(0, Math.min(90, e.touches[0].clientY - touchStart.current)));
  };
  const onTouchEnd = () => {
    if (pull > 70) {
      setLoading(true);
      refresh();
    }
    setPull(0);
    touchStart.current = null;
  };

  return (
    <div onTouchStart={onTouchStart} onTouchMove={onTouchMove} onTouchEnd={onTouchEnd} className="space-y-4">
      {pull > 0 && (
        <div className="flex justify-center" style={{ height: pull }}>
          <RefreshCw className={`h-6 w-6 text-ui-blue ${pull > 70 ? "animate-spin" : ""}`} style={{ transform: `rotate(${pull * 4}deg)` }} />
        </div>
      )}
      {header}
      {newItems > 0 && (
        <button onClick={() => { window.scrollTo({ top: 0, behavior: "smooth" }); setLoading(true); refresh(); }}
          className="btn-primary sticky top-28 sm:top-16 z-30 mx-auto flex rounded-full shadow-pop">
          <ArrowUp className="h-4 w-4" /> {newItems} bài viết mới
        </button>
      )}
      {error && <ErrorBox message={error} onRetry={() => { setLoading(true); refresh(); }} />}
      {loading && posts.length === 0 ? (
        <><LoadingCard /><LoadingCard /></>
      ) : posts.length === 0 && !error ? (
        <div className="card p-8 text-center text-ui-textSecondary">{emptyText}</div>
      ) : (
        posts.map((p) => (
          <PostCard key={`${p.id}-${p.edited_times}`} post={p} onRemoved={(id) => setPosts((prev) => prev.filter((x) => x.id !== id))} />
        ))
      )}
      <div ref={sentinel} />
      {loadingMore && <div className="flex justify-center"><Spinner /></div>}
      {!hasMore && posts.length > 0 && <p className="text-center text-sm text-ui-textMuted">Bạn đã xem hết bài viết.</p>}
    </div>
  );
}
