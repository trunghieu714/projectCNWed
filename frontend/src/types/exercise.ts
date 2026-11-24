export interface Exercise {
  id: number;
  title: string;
  category: "military" | "sword_dance" | "artistic_dance" | string;
  description?: string;
  coach_video_url: string;
  course_id?: number;
  created_by: number;
  created_at: string;
}
