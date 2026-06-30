import SearchForm from '@/components/SearchForm';

export default function HomePage() {
  return (
    <div className="min-h-screen">
      {/* Hero section */}
      <section className="relative bg-gradient-to-br from-primary-800 via-primary-700 to-primary-900 overflow-hidden">
        {/* Background pattern */}
        <div className="absolute inset-0 opacity-10">
          <svg className="w-full h-full" viewBox="0 0 1000 600" xmlns="http://www.w3.org/2000/svg">
            <circle cx="100" cy="100" r="80" fill="white" />
            <circle cx="500" cy="50" r="120" fill="white" />
            <circle cx="850" cy="150" r="100" fill="white" />
            <circle cx="200" cy="400" r="60" fill="white" />
            <circle cx="750" cy="450" r="90" fill="white" />
            <circle cx="450" cy="500" r="50" fill="white" />
          </svg>
        </div>

        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16 sm:py-24">
          <div className="text-center mb-10">
            <h1 className="text-3xl sm:text-4xl lg:text-5xl font-bold text-white mb-4">
              Đặt vé máy bay <span className="text-primary-200">dễ dàng</span>
            </h1>
            <p className="text-primary-100 text-base sm:text-lg max-w-2xl mx-auto">
              Tìm kiếm và đặt vé máy bay với giá tốt nhất từ các hãng hàng không hàng đầu Việt Nam
            </p>
          </div>

          {/* Search form */}
          <SearchForm />
        </div>
      </section>

      {/* Features section */}
      <section className="py-16 sm:py-20 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-2xl sm:text-3xl font-bold text-center text-gray-800 mb-12">
            Tại sao chọn <span className="text-primary-600">ABTrip</span>?
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-8">
            <div className="text-center p-6">
              <div className="w-14 h-14 bg-primary-100 rounded-xl flex items-center justify-center mx-auto mb-4">
                <svg className="w-7 h-7 text-primary-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <h3 className="font-semibold text-gray-800 mb-2">Đặt vé nhanh chóng</h3>
              <p className="text-gray-500 text-sm">Quy trình đặt vé đơn giản, chỉ với vài thao tác</p>
            </div>
            <div className="text-center p-6">
              <div className="w-14 h-14 bg-primary-100 rounded-xl flex items-center justify-center mx-auto mb-4">
                <svg className="w-7 h-7 text-primary-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z" />
                </svg>
              </div>
              <h3 className="font-semibold text-gray-800 mb-2">Nhiều phương thức thanh toán</h3>
              <p className="text-gray-500 text-sm">Hỗ trợ thanh toán online an toàn, tiện lợi</p>
            </div>
            <div className="text-center p-6">
              <div className="w-14 h-14 bg-primary-100 rounded-xl flex items-center justify-center mx-auto mb-4">
                <svg className="w-7 h-7 text-primary-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                </svg>
              </div>
              <h3 className="font-semibold text-gray-800 mb-2">An toàn và bảo mật</h3>
              <p className="text-gray-500 text-sm">Thông tin của bạn được bảo vệ tuyệt đối</p>
            </div>
          </div>
        </div>
      </section>

      {/* Popular routes */}
      <section className="py-16 sm:py-20 bg-gray-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-2xl sm:text-3xl font-bold text-center text-gray-800 mb-12">
            Đường bay phổ biến
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {[
              { from: 'Hà Nội', to: 'Hồ Chí Minh', code: 'HAN-SGN' },
              { from: 'Hồ Chí Minh', to: 'Hà Nội', code: 'SGN-HAN' },
              { from: 'Hà Nội', to: 'Đà Nẵng', code: 'HAN-DAD' },
              { from: 'Hồ Chí Minh', to: 'Nha Trang', code: 'SGN-CXR' },
            ].map((route) => (
              <a
                key={route.code}
                href={`/search?origin=${route.code.split('-')[0]}&destination=${route.code.split('-')[1]}`}
                className="card-hover p-4 flex items-center justify-between group"
              >
                <div>
                  <div className="font-medium text-gray-800">{route.from}</div>
                  <div className="text-sm text-gray-400">→ {route.to}</div>
                </div>
                <svg className="w-5 h-5 text-gray-300 group-hover:text-primary-500 transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                </svg>
              </a>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
