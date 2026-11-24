"use client";

import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from "react";
import { User, TokenResponse, LoginCredentials, RegisterCredentials } from "../types/auth";
import { authService } from "../services/apiClient";
import { call } from "../services/api";

interface AuthContextType {
  user: User | null;
  tokenData: TokenResponse | null;
  isAuthenticated: boolean;
  isCoach: boolean;
  isAdmin: boolean;
  /** Bí danh của tokenData cho các trang mới (session.user_id) */
  session: TokenResponse | null;
  isStudent: boolean;
  userRole: string;
  isLoading: boolean;
  login: (credentials: LoginCredentials) => Promise<User>;
  register: (credentials: RegisterCredentials) => Promise<User>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [tokenData, setTokenData] = useState<TokenResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  // Khởi tạo trạng thái ngay lập tức từ localStorage khi Client mount
  const loadUserFromStorage = useCallback(async () => {
    if (typeof window === "undefined") {
      setIsLoading(false);
      return;
    }

    const token = localStorage.getItem("access_token");
    const stored = localStorage.getItem("user_data");

    if (token && stored) {
      try {
        const parsedTokenData: TokenResponse = JSON.parse(stored);
        setTokenData(parsedTokenData);

        // Khởi tạo ngay lập tức user tối thiểu để UI không bị gián đoạn/nhấp nháy chữ Đăng Nhập
        const fallbackUser: User = {
          id: parsedTokenData.user_id,
          username: parsedTokenData.username,
          role: parsedTokenData.role,
          phonenumber: parsedTokenData.phonenumber,
          is_active: true,
          created_at: new Date().toISOString(),
        };
        setUser(fallbackUser);

        // Xác thực và lấy đầy đủ profile từ backend
        try {
          const profile = await authService.getMe();
          setUser(profile);
        } catch (apiErr: any) {
          // Chỉ logout nếu thực sự bị 401 (token hết hạn)
          if (apiErr?.response?.status === 401) {
            authService.logout();
            setUser(null);
            setTokenData(null);
          }
        }
      } catch (err) {
        authService.logout();
        setUser(null);
        setTokenData(null);
      }
    } else {
      setUser(null);
      setTokenData(null);
    }
    setIsLoading(false);
  }, []);

  useEffect(() => {
    loadUserFromStorage();

    // Lắng nghe sự kiện storage để đồng bộ giữa các tab
    const handleStorageChange = () => {
      loadUserFromStorage();
    };
    window.addEventListener("storage", handleStorageChange);
    return () => window.removeEventListener("storage", handleStorageChange);
  }, [loadUserFromStorage]);

  const login = async (credentials: LoginCredentials): Promise<User> => {
    setIsLoading(true);
    try {
      const res = await authService.login(credentials);
      setTokenData(res);

      // Thiết lập ngay lập tức user tối thiểu từ res
      const immediateUser: User = {
        id: res.user_id,
        username: res.username,
        role: res.role,
        phonenumber: res.phonenumber,
        is_active: true,
        created_at: new Date().toISOString(),
      };
      setUser(immediateUser);

      // Lấy profile đầy đủ
      try {
        const profile = await authService.getMe();
        setUser(profile);
        return profile;
      } catch {
        return immediateUser;
      }
    } finally {
      setIsLoading(false);
    }
  };

  const register = async (credentials: RegisterCredentials): Promise<User> => {
    setIsLoading(true);
    try {
      const res = await authService.register(credentials);
      setTokenData(res);

      const immediateUser: User = {
        id: res.user_id,
        username: res.username,
        role: res.role,
        full_name: credentials.full_name,
        email: credentials.email,
        is_active: true,
        created_at: new Date().toISOString(),
      };
      setUser(immediateUser);

      try {
        const profile = await authService.getMe();
        setUser(profile);
        return profile;
      } catch {
        return immediateUser;
      }
    } finally {
      setIsLoading(false);
    }
  };

  const logout = () => {
    // Hủy phiên trên server (token cũ hết hiệu lực) rồi mới xóa ở trình duyệt
    call("logout").catch(() => {});
    authService.logout();
    setUser(null);
    setTokenData(null);
  };

  const rawRole = (user?.role || tokenData?.role || "").toString().toLowerCase();
  const isCoach = rawRole === "coach" || rawRole === "admin";
  const isStudent = rawRole === "student";
  const isAdmin = rawRole === "admin";

  const isAuthenticated = !!(user || tokenData);

  return (
    <AuthContext.Provider
      value={{
        user,
        tokenData,
        isAuthenticated,
        isCoach,
        isAdmin,
        session: tokenData,
        isStudent,
        userRole: rawRole,
        isLoading,
        login,
        register,
        logout,
        refreshUser: loadUserFromStorage,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
