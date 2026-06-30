import type { Metadata } from 'next';
import '@/globals.css';
import Header from '@/components/Header';

export const metadata: Metadata = {
  title: 'ABTrip - Đặt vé máy bay, Tour, Visa & Hộ chiếu',
  description: 'Hệ thống đặt vé máy bay, tour du lịch và hỗ trợ visa hộ chiếu trực tuyến - ABTrip. Dịch vụ du lịch toàn diện.',
  keywords: ['vé máy bay', 'đặt vé', 'ABTrip', 'tour du lịch', 'visa', 'hộ chiếu', 'du lịch'],
  openGraph: {
    title: 'ABTrip - Dịch vụ du lịch toàn diện',
    description: 'Đặt vé máy bay, tour du lịch và hỗ trợ visa hộ chiếu',
    type: 'website',
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="vi">
      <body>
        <div className="min-h-screen flex flex-col">
          <Header />
          <main className="flex-1">
            {children}
          </main>
          <footer className="bg-gray-800 text-gray-400 py-8">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-8">
                <div>
                  <h3 className="text-white font-semibold mb-3">ABTrip</h3>
                  <p className="text-sm">
                    Hệ thống đặt vé máy bay, tour du lịch và hỗ trợ visa hộ chiếu hàng đầu Việt Nam.
                  </p>
                </div>
                <div>
                  <h3 className="text-white font-semibold mb-3">Liên hệ</h3>
                  <p className="text-sm">Email: support@abtrip.vn</p>
                  <p className="text-sm">Hotline: 1900 XXX XXX</p>
                </div>
                <div>
                  <h3 className="text-white font-semibold mb-3">Dịch vụ</h3>
                  <p className="text-sm">Đặt vé máy bay</p>
                  <p className="text-sm">Tour du lịch</p>
                  <p className="text-sm">Visa & Hộ chiếu</p>
                </div>
              </div>
              <div className="border-t border-gray-700 mt-8 pt-6 text-center text-sm">
                &copy; {new Date().getFullYear()} ABTrip. Tất cả quyền được bảo lưu.
              </div>
            </div>
          </footer>
        </div>
      </body>
    </html>
  );
}
