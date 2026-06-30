import Link from 'next/link';

export default function Header() {
  return (
    <header className="bg-white border-b border-gray-200 shadow-sm sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <Link href="/" className="flex items-center gap-2 group">
            <div className="w-9 h-9 bg-primary-600 rounded-lg flex items-center justify-center group-hover:bg-primary-700 transition-colors">
              <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
              </svg>
            </div>
            <span className="text-xl font-bold text-gray-800">
              <span className="text-primary-600">AB</span>Trip
            </span>
          </Link>

          {/* Navigation */}
          <nav className="flex items-center gap-4 sm:gap-6">
            <Link
              href="/"
              className="text-sm font-medium text-gray-600 hover:text-primary-600 transition-colors"
            >
              Trang chủ
            </Link>
            <Link
              href="/search"
              className="text-sm font-medium text-gray-600 hover:text-primary-600 transition-colors"
            >
              Tra cứu
            </Link>
          </nav>
        </div>
      </div>
    </header>
  );
}
