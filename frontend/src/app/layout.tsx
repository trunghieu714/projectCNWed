import type { Metadata } from "next";
import "./globals.css";
import { Navbar } from "../components/common/Navbar";
import { Footer } from "../components/common/Footer";
import { AuthProvider } from "../context/AuthContext";

export const metadata: Metadata = {
  title: "Skill Assessment Platform - AI Motion Coaching",
  description:
    "Hệ thống Đánh giá Kỹ năng Vận động qua Video sử dụng Pose Estimation 3D + DTW kết hợp Mạng Xã Hội Luyện Tập",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="vi">
      <body className="flex flex-col min-h-screen bg-slate-950 text-slate-100 antialiased selection:bg-blue-600 selection:text-white">
        <AuthProvider>
          <Navbar />
          <main className="flex-1">{children}</main>
          <Footer />
        </AuthProvider>
      </body>
    </html>
  );
}
