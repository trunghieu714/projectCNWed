"use client";

import React, { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { call, errorMessage } from "../../../services/api";
import { SpecPost } from "../../../types/spec";
import { ErrorBox, LoadingCard } from "../../../components/common/ui";
import { PostCard } from "../../../components/feed/PostCard";

export default function PostDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [post, setPost] = useState<SpecPost | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setPost(null);
    call<SpecPost>("get_post", { id })
      .then(setPost)
      .catch((e) => setError(errorMessage(e)));
  }, [id]);

  useEffect(() => {
    // Bài nộp đang chấm: tải lại để thấy điểm của AI bot
    if (!post?.submission || ["COMPLETED", "FAILED"].includes(post.submission.status)) return;
    const t = setTimeout(() => call<SpecPost>("get_post", { id }).then(setPost).catch(() => {}), 4000);
    return () => clearTimeout(t);
  }, [post, id]);

  return (
    <div className="mx-auto max-w-[680px] px-2 py-4">
      {error ? <ErrorBox message={error} /> : post ? <PostCard key={`${post.id}-${post.submission?.status}`} post={post} /> : <LoadingCard />}
    </div>
  );
}
