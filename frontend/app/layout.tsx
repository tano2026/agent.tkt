import type { Metadata } from "next";
import "../globals.css";

export const metadata: Metadata = {
  title: "ABTrip AI Agent — Đặt vé, eSIM & Visa thông minh",
  description: "Trợ lý AI cho phòng vé — đặt vé máy bay, mua eSIM du lịch, tư vấn visa & hộ chiếu.",
  viewport: "width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="vi">
      <body className="antialiased bg-gray-50">{children}</body>
    </html>
  );
}
