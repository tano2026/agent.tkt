'use client';

import { useState } from 'react';

const visaTypes = [
  { value: 'tourist', label: 'Visa du lịch' },
  { value: 'business', label: 'Visa công tác' },
  { value: 'student', label: 'Visa du học' },
  { value: 'transit', label: 'Visa quá cảnh' },
  { value: 'work', label: 'Visa lao động' },
];

const countries = [
  'Thái Lan', 'Singapore', 'Malaysia', 'Nhật Bản', 'Hàn Quốc',
  'Trung Quốc', 'Mỹ', 'Anh', 'Pháp', 'Đức', 'Úc', 'Canada',
  'Ấn Độ', 'Dubai', 'Thổ Nhĩ Kỳ', 'Nga', 'Ý', 'Tây Ban Nha',
];

export default function VisaAgent() {
  const [visaType, setVisaType] = useState('');
  const [country, setCountry] = useState('');
  const [fullName, setFullName] = useState('');
  const [passportNumber, setPassportNumber] = useState('');
  const [nationality, setNationality] = useState('Việt Nam');
  const [showCountryDropdown, setShowCountryDropdown] = useState(false);

  const filteredCountries = countries.filter((c) =>
    c.toLowerCase().includes(country.toLowerCase())
  );

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    alert('🔧 Visa Agent đang phát triển — tính năng sẽ sớm ra mắt!');
  };

  return (
    <div className="w-full max-w-4xl mx-auto">
      {/* Header */}
      <div className="text-center mb-8">
        <div className="inline-flex items-center justify-center w-16 h-16 bg-violet-100 rounded-2xl mb-4">
          <svg className="w-8 h-8 text-violet-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6v3.75m0 3v.75M12 6v3.75m0 3v.75M8.25 6v3.75m0 3v.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </div>
        <h2 className="text-2xl font-bold text-gray-800 mb-2">Visa & Hộ chiếu</h2>
        <p className="text-gray-500">Hỗ trợ xin visa, gia hạn hộ chiếu và các thủ tục xuất nhập cảnh</p>
      </div>

      <form onSubmit={handleSubmit} className="card p-6 space-y-4">
        {/* Visa type */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Loại visa</label>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
            {visaTypes.map((vt) => (
              <button
                key={vt.value}
                type="button"
                onClick={() => setVisaType(vt.value)}
                className={`px-4 py-2.5 rounded-lg border text-sm font-medium transition-all ${
                  visaType === vt.value
                    ? 'border-violet-500 bg-violet-50 text-violet-700'
                    : 'border-gray-200 bg-white text-gray-600 hover:border-violet-300 hover:bg-violet-50/50'
                }`}
              >
                {vt.label}
              </button>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {/* Country */}
          <div className="relative">
            <label className="block text-sm font-medium text-gray-700 mb-1">Quốc gia đến</label>
            <input
              type="text"
              className="input-field"
              placeholder="Tìm quốc gia..."
              value={country}
              onChange={(e) => {
                setCountry(e.target.value);
                setShowCountryDropdown(true);
              }}
              onFocus={() => setShowCountryDropdown(true)}
            />
            {showCountryDropdown && (
              <div className="absolute z-10 mt-1 w-full bg-white border border-gray-200 rounded-lg shadow-lg max-h-48 overflow-y-auto">
                {filteredCountries.length === 0 ? (
                  <div className="p-3 text-sm text-gray-500">Không tìm thấy</div>
                ) : (
                  filteredCountries.map((c) => (
                    <button
                      key={c}
                      type="button"
                      className="w-full text-left px-4 py-2.5 hover:bg-violet-50 text-sm transition-colors"
                      onClick={() => {
                        setCountry(c);
                        setShowCountryDropdown(false);
                      }}
                    >
                      {c}
                    </button>
                  ))
                )}
              </div>
            )}
          </div>

          {/* Nationality */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Quốc tịch</label>
            <input
              type="text"
              className="input-field bg-gray-50"
              value={nationality}
              readOnly
            />
            <p className="text-xs text-gray-400 mt-1">Hiện tại hỗ trợ công dân Việt Nam</p>
          </div>
        </div>

        {/* Personal info */}
        <div className="border-t border-gray-100 pt-4">
          <h3 className="text-sm font-semibold text-gray-600 mb-3">Thông tin cá nhân</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Họ và tên</label>
              <input
                type="text"
                className="input-field"
                placeholder="Nhập họ và tên đầy đủ"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Số hộ chiếu</label>
              <input
                type="text"
                className="input-field"
                placeholder="Ví dụ: B1234567"
                value={passportNumber}
                onChange={(e) => setPassportNumber(e.target.value)}
              />
            </div>
          </div>
        </div>

        <button type="submit" className="btn-primary w-full sm:w-auto sm:px-12 py-3 text-base">
          Tra cứu thủ tục
        </button>
      </form>

      {/* Service list */}
      <div className="mt-8 grid grid-cols-1 sm:grid-cols-3 gap-4">
        {[
          { title: 'Xin visa du lịch', desc: 'Hỗ trợ hồ sơ xin visa các nước', icon: '🛂', color: 'violet' },
          { title: 'Gia hạn hộ chiếu', desc: 'Làm mới và gia hạn hộ chiếu', icon: '📄', color: 'violet' },
          { title: 'Dịch thuật công chứng', desc: 'Dịch thuật hồ sơ xin visa', icon: '🌐', color: 'violet' },
        ].map((item) => (
          <div key={item.title} className="card p-4 text-center opacity-60">
            <div className="text-2xl mb-2">{item.icon}</div>
            <div className="font-medium text-gray-800 text-sm">{item.title}</div>
            <div className="text-xs text-gray-400 mt-1">{item.desc}</div>
            <div className="mt-2 text-xs text-violet-500 font-medium">Sắp ra mắt →</div>
          </div>
        ))}
      </div>
    </div>
  );
}
