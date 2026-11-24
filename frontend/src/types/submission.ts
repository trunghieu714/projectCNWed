import { User } from "./auth";

export type SubmissionStatus = "PENDING" | "PROCESSING" | "COMPLETED" | "FAILED";

export interface FrameError {
  coach_frame: number;
  student_frame: number;
  max_angle_error: number;
  status: "INCORRECT" | "CORRECT";
}

export interface SubmissionResponse {
  id: number;
  exercise_id: number;
  student_id: number;
  student_video_url: string;
  coach_video_url?: string;
  fused_video_url?: string;
  status: SubmissionStatus;
  score?: number;
  feedback_text?: string;
  error_message?: string;
  task_id?: string;
  created_at: string;
  warping_path?: [number, number][];
  errors?: FrameError[];
  student?: User;
}
