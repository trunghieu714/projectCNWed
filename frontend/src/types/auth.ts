export type UserRole = "student" | "coach" | "admin" | "STUDENT" | "COACH" | "ADMIN" | string;

export interface User {
  id: number;
  username: string;
  email?: string;
  phonenumber?: string;
  full_name?: string;
  height?: number;
  avatar_url?: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  role: UserRole;
  user_id: number;
  username: string;
  phonenumber?: string;
}

export interface LoginCredentials {
  username_or_email: string;
  password: string;
}

export interface RegisterCredentials {
  username: string;
  email: string;
  password: string;
  full_name?: string;
  role: UserRole;
}
