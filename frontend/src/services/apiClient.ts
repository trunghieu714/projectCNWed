import axios from "axios";
import { SubmissionResponse } from "../types/submission";
import { Exercise } from "../types/exercise";
import { User, TokenResponse, LoginCredentials, RegisterCredentials } from "../types/auth";
import { Post, CreatePostInput, CommentItem } from "../types/post";
import { Course, CourseMember } from "../types/course";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
});

// Tự động gắn Bearer Token vào Header nếu đã đăng nhập
apiClient.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("access_token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

// Xử lý lỗi 401 tự động
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    // API mới trả lỗi dạng {code, message}: chép sang "detail" để các màn hình cũ hiển thị đúng thông báo
    const data = error.response?.data;
    if (data && data.detail === undefined && typeof data.message === "string") {
      data.detail = data.message;
    }
    if (error.response?.status === 401 && typeof window !== "undefined") {
      localStorage.removeItem("access_token");
      localStorage.removeItem("user_data");
    }
    return Promise.reject(error);
  }
);

// 1. Authentication Services
export const authService = {
  async login(credentials: LoginCredentials): Promise<TokenResponse> {
    const formData = new URLSearchParams();
    formData.append("username", credentials.username_or_email);
    formData.append("password", credentials.password);

    const response = await apiClient.post<TokenResponse>("/auth/login", formData, {
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
    });
    
    if (typeof window !== "undefined") {
      localStorage.setItem("access_token", response.data.access_token);
      localStorage.setItem("user_data", JSON.stringify(response.data));
    }
    return response.data;
  },

  async register(data: RegisterCredentials): Promise<TokenResponse> {
    const response = await apiClient.post<TokenResponse>("/auth/register", data);
    if (typeof window !== "undefined") {
      localStorage.setItem("access_token", response.data.access_token);
      localStorage.setItem("user_data", JSON.stringify(response.data));
    }
    return response.data;
  },

  async getMe(): Promise<User> {
    const response = await apiClient.get<User>("/auth/me");
    return response.data;
  },

  logout(): void {
    if (typeof window !== "undefined") {
      localStorage.removeItem("access_token");
      localStorage.removeItem("user_data");
    }
  },
};

// 2. Exercise Services
export const exerciseService = {
  async getExercises(category?: string): Promise<Exercise[]> {
    const params = category && category !== "all" ? { category } : {};
    const response = await apiClient.get<Exercise[]>("/exercises/", { params });
    return response.data;
  },

  async getExerciseById(id: number): Promise<Exercise> {
    const response = await apiClient.get<Exercise>(`/exercises/${id}`);
    return response.data;
  },

  async createExercise(formData: FormData): Promise<Exercise> {
    const response = await apiClient.post<Exercise>("/exercises/", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return response.data;
  },
};

// 3. Course Services (Slide 25 & 27)
export const courseService = {
  async getCourses(): Promise<Course[]> {
    const response = await apiClient.get<{ code: string; data: Course[] }>("/courses/");
    return response.data.data;
  },

  async getCourseById(id: number): Promise<Course> {
    const response = await apiClient.get<{ code: string; data: Course }>(`/courses/${id}`);
    return response.data.data;
  },

  async createCourse(title: string, description?: string, maxStudents: number = 500): Promise<Course> {
    const response = await apiClient.post<{ code: string; data: Course }>("/courses/", {
      title,
      description,
      max_students: maxStudents,
    });
    return response.data.data;
  },

  async enrollCourse(courseId: number): Promise<CourseMember> {
    const response = await apiClient.post<{ code: string; data: CourseMember }>(`/courses/${courseId}/enroll`);
    return response.data.data;
  },
};

// 4. Submission Services
export const submissionService = {
  async submitExercise(exerciseId: number, videoFile: File): Promise<SubmissionResponse> {
    const formData = new FormData();
    formData.append("exercise_id", exerciseId.toString());
    formData.append("file", videoFile);

    const response = await apiClient.post<SubmissionResponse>("/submissions/submit", formData, {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    });
    return response.data;
  },

  async getSubmission(submissionId: number): Promise<SubmissionResponse> {
    const response = await apiClient.get<SubmissionResponse>(`/submissions/${submissionId}`);
    return response.data;
  },

  async getMyHistory(): Promise<SubmissionResponse[]> {
    const response = await apiClient.get<SubmissionResponse[]>("/submissions/my-history");
    return response.data;
  },

  async getExerciseSubmissions(exerciseId: number): Promise<SubmissionResponse[]> {
    const response = await apiClient.get<SubmissionResponse[]>(`/submissions/exercise/${exerciseId}`);
    return response.data;
  },
};

// 5. Social Feed & Post Services (Slide 6 & 7)
export const postService = {
  async getFeed(): Promise<Post[]> {
    const response = await apiClient.get<Post[]>("/posts/");
    return response.data;
  },

  async createPost(input: CreatePostInput): Promise<Post> {
    const response = await apiClient.post<Post>("/posts/", input);
    return response.data;
  },

  async addPostWithVideos(formData: FormData): Promise<any> {
    const response = await apiClient.post<{ code: string; data: any }>("/posts/add_post", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return response.data.data;
  },

  async editPost(postId: number, formData: FormData): Promise<any> {
    const response = await apiClient.post<{ code: string; data: any }>(`/posts/${postId}/edit_post`, formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return response.data.data;
  },

  async getComments(postId: number): Promise<CommentItem[]> {
    const response = await apiClient.get<{ code: string; data: CommentItem[] }>(`/posts/${postId}/comments`);
    return response.data.data;
  },

  async addComment(postId: number, content: string): Promise<CommentItem> {
    const response = await apiClient.post<{ code: string; data: CommentItem }>(`/posts/${postId}/comments`, {
      content,
    });
    return response.data.data;
  },

  async likePost(postId: number): Promise<{ status: string; likes_count: number }> {
    const response = await apiClient.post<{ status: string; likes_count: number }>(`/posts/${postId}/like`);
    return response.data;
  },
};
