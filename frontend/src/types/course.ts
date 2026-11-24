import { PostAuthor } from "./post";

export interface Course {
  id: number;
  teacher_id: number;
  title: string;
  description?: string;
  max_students: number;
  created_at: string;
  teacher?: PostAuthor;
  students_count?: number;
}

export interface CourseMember {
  id: number;
  course_id: number;
  student_id: number;
  status: "PENDING" | "APPROVED" | "REJECTED";
  joined_at: string;
}
