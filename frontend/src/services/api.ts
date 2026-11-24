/**
 * Client cho bộ API theo đặc tả: POST {BASE}/api/<tên_api>, tham số gửi dạng multipart form-data,
 * token trong tham số `token`. Response {code, message, data}; code khác "1000" -> ném ApiError.
 */
import axios from "axios";
import { MESSAGES } from "../lib/validation";

const V1 = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
export const BACKEND_BASE = V1.replace(/\/api\/v1\/?$/, "");
export const SPEC_BASE = `${BACKEND_BASE}/api`;

export class ApiError extends Error {
  code: string;
  data: any;
  constructor(code: string, message: string, data?: any) {
    super(message);
    this.code = code;
    this.data = data;
  }
}

export type Params = Record<string, string | number | boolean | File | null | undefined>;

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return localStorage.getItem("access_token");
  } catch {
    return null;
  }
}

export function clearSession() {
  try {
    localStorage.removeItem("access_token");
    localStorage.removeItem("user_data");
  } catch {}
}

export async function call<T = any>(name: string, params: Params = {}, opts: { auth?: boolean } = {}): Promise<T> {
  if (typeof navigator !== "undefined" && !navigator.onLine) {
    throw new ApiError("NETWORK", MESSAGES.network);
  }
  const form = new FormData();
  const token = opts.auth === false ? null : getToken();
  if (token) form.append("token", token);
  Object.entries(params).forEach(([k, v]) => {
    if (v === undefined || v === null || v === "") return;
    if (v instanceof File) form.append(k, v, v.name);
    else form.append(k, typeof v === "boolean" ? (v ? "1" : "0") : String(v));
  });
  try {
    const res = await axios.post(`${SPEC_BASE}/${name}`, form, { timeout: 15 * 60 * 1000 });
    const body = res.data;
    if (!body || typeof body.code !== "string") throw new ApiError("FORMAT", MESSAGES.server);
    if (body.code !== "1000") throw new ApiError(body.code, body.message, body.data);
    return body.data as T;
  } catch (err: any) {
    if (err instanceof ApiError) throw err;
    const body = err?.response?.data;
    if (body && typeof body.code === "string") {
      if (body.code === "9998" || (err.response.status === 401 && token)) {
        // Token sai / hết hạn / đăng nhập ở máy khác -> về màn hình đăng nhập
        clearSession();
        if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
          window.location.href = `/login?reason=${encodeURIComponent(body.message || "")}`;
        }
      }
      throw new ApiError(body.code, body.message, body.data);
    }
    if (!err?.response) throw new ApiError("NETWORK", MESSAGES.network);
    throw new ApiError("FORMAT", MESSAGES.server);
  }
}

export function errorMessage(err: unknown): string {
  if (err instanceof ApiError) return err.message;
  return MESSAGES.server;
}

export function mediaUrl(path?: string | null): string {
  if (!path) return "";
  if (/^(https?:|blob:|data:)/.test(path)) return path;
  return `${BACKEND_BASE}/${path.replace(/^\//, "")}`;
}
