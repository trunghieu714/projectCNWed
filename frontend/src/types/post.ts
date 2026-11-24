import { SubmissionResponse } from "./submission";

export interface PostAuthor {
  id: number | null;
  username: string;
  full_name?: string | null;
  name?: string;
  role: string;
  role_label?: string;
  avatar_url?: string | null;
  avatar?: string | null;
}

export interface CommentItem {
  id: number;
  post_id: number;
  user_id?: number | null;
  content: string;
  is_bot_evaluation: boolean;
  created_at: string;
  user?: PostAuthor;
  /** Điểm số & xâu HTML chi tiết lỗi do AI bot gửi (set_comment) */
  score?: number | null;
  detail_mistakes?: string | null;
}

export interface Post {
  id: number;
  user_id: number;
  course_id?: number | null;
  exercise_id?: number | null;
  submission_id?: number | null;
  content: string;
  video_left_url?: string | null;
  video_right_url?: string | null;
  video_fused_url?: string | null;
  device_master?: string | null;
  device_slave?: string | null;
  likes_count: number;
  created_at: string;
  updated_at?: string | null;
  author?: PostAuthor;
  submission?: Pick<SubmissionResponse, "id"> & Partial<Pick<SubmissionResponse, "score" | "feedback_text" | "status">> | null;
  comments?: CommentItem[];
  // Các trường bổ sung từ server (API theo đặc tả)
  is_liked?: boolean;
  comments_count?: number;
  is_exercise?: boolean;
  submissions_count?: number;
  edited_times?: number;
  can_edit?: boolean;
  can_delete?: boolean;
  can_submit?: boolean;
  lecturer?: PostAuthor | null;
  thumbnail_url?: string | null;
}

export interface CreatePostInput {
  content: string;
  submission_id?: number;
  course_id?: number;
  exercise_id?: number;
  video_left_url?: string;
  video_right_url?: string;
}
