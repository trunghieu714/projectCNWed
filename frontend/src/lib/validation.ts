/**
 * Quy tắc kiểm tra dữ liệu phía client - giống hệt phía server (backend/app/core/text_rules.py).
 * Thông báo dùng chung một câu cho mọi màn hình (Slide 34): đăng nhập và đăng ký cùng báo
 * "Số điện thoại không đúng định dạng."
 */
export const MESSAGES = {
  phone: "Số điện thoại không đúng định dạng.",
  password: "Mật khẩu phải từ 6 đến 30 ký tự, không chứa ký tự đặc biệt và không trùng số điện thoại.",
  network: "Mất kết nối mạng. Vui lòng kiểm tra Internet và thử lại.",
  server: "Không kết nối được máy chủ hoặc dữ liệu trả về không đúng định dạng.",
};

export const MAX_WORDS = 500;
export const MIN_VIDEO_SECONDS = 10;
export const MAX_VIDEO_MB = 150;
export const VIDEO_EXTENSIONS = [".mp4", ".avi", ".mov", ".mkv", ".webm"];

export function phoneError(phone: string): string | null {
  return /^0\d{9}$/.test((phone || "").trim()) ? null : MESSAGES.phone;
}

export function passwordError(password: string, phone?: string): string | null {
  if (!/^[A-Za-z0-9]{6,30}$/.test(password || "")) return MESSAGES.password;
  if (phone && password === phone.trim()) return MESSAGES.password;
  return null;
}

export function usernameError(name: string, phone?: string): string | null {
  const v = (name || "").trim();
  if (!v) return "Tên người dùng không được để trống.";
  if (v.length < 2 || v.length > 50) return "Tên người dùng phải từ 2 đến 50 ký tự.";
  if (/[<>{}\[\]\\/@#$%^&*=+|~`"';:!?]/.test(v)) return "Tên người dùng không được chứa ký tự đặc biệt.";
  if (/(https?:\/\/|www\.)/i.test(v) || /\.(com|vn|net|org)\b/i.test(v)) return "Tên người dùng không được là đường dẫn.";
  const digits = v.replace(/\D/g, "");
  if ((phone && digits === phone.trim()) || /^[\d\s+.-]{8,}$/.test(v)) return "Tên người dùng không được là số điện thoại.";
  return null;
}

export function countWords(text: string): number {
  return (text || "").trim().split(/\s+/).filter(Boolean).length;
}

export function wordLimitError(text: string, limit = MAX_WORDS): string | null {
  return countWords(text) > limit ? `Nội dung vượt quá ${limit} từ.` : null;
}

/** Đọc thời lượng video ngay trên trình duyệt (không cần upload). */
export function readVideoDuration(file: File): Promise<number | null> {
  return new Promise((resolve) => {
    const url = URL.createObjectURL(file);
    const video = document.createElement("video");
    video.preload = "metadata";
    const done = (v: number | null) => {
      URL.revokeObjectURL(url);
      resolve(v);
    };
    video.onloadedmetadata = () => done(Number.isFinite(video.duration) ? video.duration : null);
    video.onerror = () => done(null);
    video.src = url;
  });
}

/** Kiểm tra video trước khi gửi (Slide 33: dữ liệu được kiểm tra ở client trước). */
export async function videoError(file: File): Promise<string | null> {
  const ext = "." + (file.name.split(".").pop() || "").toLowerCase();
  if (!VIDEO_EXTENSIONS.includes(ext)) return `Định dạng ${ext} không được hỗ trợ (chỉ ${VIDEO_EXTENSIONS.join(", ")}).`;
  if (file.size > MAX_VIDEO_MB * 1024 * 1024) return `Dung lượng video quá lớn (tối đa ${MAX_VIDEO_MB}MB).`;
  const duration = await readVideoDuration(file);
  if (duration !== null && duration + 0.05 < MIN_VIDEO_SECONDS) {
    return `Thời lượng video quá ngắn (${duration.toFixed(1)}s). Tối thiểu ${MIN_VIDEO_SECONDS} giây.`;
  }
  return null;
}
