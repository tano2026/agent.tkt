import type { Metadata } from 'next';
import '@/globals.css';

export const metadata: Metadata = {
  title: 'ABTrip - Đặt vé máy bay, Tour, Visa & Hộ chiếu',
  description: 'ABTrip AI Agent - Đặt vé máy bay, SIM du lịch, tư vấn visa bằng chat tự nhiên',
  manifest: '/manifest.json',
  viewport: 'width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="vi">
      <head>
        <meta name="theme-color" content="#2563eb" />
        <meta name="apple-mobile-web-app-capable" content="yes" />
        <meta name="apple-mobile-web-app-status-bar-style" content="default" />
      </head>
      <body>{children}</body>
    </html>
  );
}
