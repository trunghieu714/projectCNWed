/**
 * Helper chuẩn hóa URL video từ Backend FastAPI để thẻ <video> của trình duyệt phát được 100%.
 * Hỗ trợ cả đường dẫn tương đối ("storage/...") và đường dẫn tuyệt đối ("http://...").
 */
export function getVideoUrl(path?: string | null): string {
  if (!path) return "";

  // Nếu đã là URL tuyệt đối có giao thức http/https/blob
  if (path.startsWith("http://") || path.startsWith("https://") || path.startsWith("blob:")) {
    return path;
  }

  // Chuẩn hóa dấu gạch chéo đầu đường dẫn
  const cleanPath = path.startsWith("/") ? path.slice(1) : path;

  // Lấy gốc domain của Backend (mặc định http://localhost:8000)
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
  const backendBase = apiUrl.replace(/\/api\/v1\/?$/, "");

  return `${backendBase}/${cleanPath}`;
}
