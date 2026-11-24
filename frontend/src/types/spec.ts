// Kiểu dữ liệu trả về từ bộ API theo đặc tả (backend/app/api/spec)

export interface UserBrief {
  id: number | null;
  username: string;
  name: string;
  full_name?: string | null;
  avatar?: string | null;
  role: string; // coach | student | admin | bot
  role_label: string; // GV | HV | ADMIN | BOT
}

export interface VideoItem {
  side: "left" | "right";
  url: string;
  thumb?: string | null;
}

export interface SubmissionBrief {
  id: number;
  status: "PENDING" | "PROCESSING" | "COMPLETED" | "FAILED";
  score?: number | null;
  feedback_text?: string | null;
  fused_video_url?: string | null;
  report_html_url?: string | null;
  error_message?: string | null;
}

export interface SpecPost {
  id: number;
  user_id: number;
  described: string;
  // Tên trường cũ (server trả về cả hai) để dùng chung PostCard của giao diện gốc
  content: string;
  likes_count: number;
  created_at: string;
  created: string;
  modified?: string;
  like: number;
  comment: number;
  is_liked: boolean;
  video: VideoItem[];
  video_left_url?: string | null;
  video_right_url?: string | null;
  video_fused_url?: string | null;
  thumbnail_url?: string | null;
  author: UserBrief;
  lecturer?: UserBrief | null;
  course_id?: number | null;
  exercise_id?: number | null;
  is_exercise: boolean;
  submission_id?: number | null;
  submission?: SubmissionBrief | null;
  submissions_count?: number;
  edited_times: number;
  is_blocked: boolean;
  can_edit: boolean;
  can_delete: boolean;
  can_submit: boolean;
  banned: boolean;
}

export interface PostList {
  posts: SpecPost[];
  new_items: number;
  last_id: number;
  total: number;
}

export interface SpecComment {
  id: number;
  post_id: number;
  user_id: number | null;
  comment: string;
  created: string;
  poster: UserBrief;
  is_bot_evaluation: boolean;
  score?: number | null;
  detail_mistakes?: string | null;
  is_blocked: boolean;
}

export interface UserInfo {
  id: number;
  username: string;
  full_name?: string | null;
  avatar?: string | null;
  cover_image?: string | null;
  description?: string | null;
  height?: number | null;
  created: string;
  role: string;
  role_label: string;
  listing: number;
  followed: number;
  is_related: boolean;
  is_blocked: boolean;
  online: boolean;
  phonenumber?: string;
  email?: string;
}

export interface CourseInfo {
  id: number; // = id giáo viên
  internal_id: number;
  title: string;
  description?: string | null;
  max_students: number;
  students_count: number;
  teacher: UserBrief;
  created: string;
  my_status?: "PENDING" | "APPROVED" | "REJECTED" | null;
  status?: string;
}

export interface NotificationItem {
  id: number;
  type: string;
  object_id?: number | null;
  title: string;
  body?: string | null;
  created: string;
  read: boolean;
  actor?: UserBrief | null;
}

export interface ChatMessage {
  id: number;
  conversation_id: number;
  message: string;
  sender: UserBrief;
  sender_id: number;
  created: string;
  unread: boolean;
}

export interface ConversationItem {
  id: number;
  partner: UserBrief;
  lastmessage: { message: string; created: string; unread: boolean; sender_id: number };
  unread_count: number;
}
