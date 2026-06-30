'use client';

import { useState } from 'react';
import SearchForm from '@/components/SearchForm';
import TourAgent from '@/components/TourAgent';
import VisaAgent from '@/components/VisaAgent';

const agents = [
  {
    id: 'ticketing',
    label: 'Vé máy bay',
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
      </svg>
    ),
    gradient: 'from-primary-800 via-primary-700 to-primary-900',
    color: 'primary',
  },
  {
    id: 'tour',
    label: 'Tour du lịch',
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5" />
      </svg>
    ),
    gradient: 'from-emerald-800 via-emerald-700 to-emerald-900',
    color: 'emerald',
  },
  {
    id: 'visa',
    label: 'Visa & Hộ chiếu',
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6v3.75m0 3v.75M12 6v3.75m0 3v.75M8.25 6v3.75m0 3v.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
    gradient: 'from-violet-800 via-violet-700 to-violet-900',
    color: 'violet',
  },
];

export default function HomePage() {
  const [activeTab, setActiveTab] = useState('ticketing');

  const activeAgent = agents.find((a) => a.id === activeTab)!;

  return (
    <div className="min-h-screen">
      {/* Hero section */}
      <section className={`relative bg-gradient-to-br ${activeAgent.gradient} overflow-hidden transition-all duration-500`}>
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

        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 sm:py-14">
          {/* Agent tabs */}
          <div className="flex justify-center mb-6">
            <div className="inline-flex bg-white/10 backdrop-blur-sm rounded-2xl p-1.5 gap-1">
              {agents.map((agent) => {
                const isActive = activeTab === agent.id;
                return (
                  <button
                    key={agent.id}
                    onClick={() => setActiveTab(agent.id)}
                    className={`
                      flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-medium
                      transition-all duration-200 whitespace-nowrap
                      ${isActive
                        ? 'bg-white text-gray-800 shadow-sm'
                        : 'text-white/70 hover:text-white hover:bg-white/10'
                      }
                    `}
                  >
                    <span className={isActive ? `text-${agent.color}-600` : 'text-white/70'}>
                      {agent.icon}
                    </span>
                    {agent.label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Hero content per tab */}
          <div className="text-center mb-8">
            <h1 className="text-2xl sm:text-3xl lg:text-4xl font-bold text-white mb-2 transition-all">
              {activeTab === 'ticketing' && <>Đặt vé máy bay <span className="text-primary-200">dễ dàng</span></>}
              {activeTab === 'tour' && <>Tour du lịch <span className="text-emerald-200">hấp dẫn</span></>}
              {activeTab === 'visa' && <>Visa & Hộ chiếu <span className="text-violet-200">nhanh chóng</span></>}
            </h1>
            <p className="text-white/70 text-sm sm:text-base max-w-xl mx-auto">
              {activeTab === 'ticketing' && 'Tìm kiếm và đặt vé máy bay với giá tốt nhất từ các hãng hàng không'}
              {activeTab === 'tour' && 'Khám phá những tour du lịch hấp dẫn với giá tốt nhất'}
              {activeTab === 'visa' && 'Hỗ trợ xin visa, gia hạn hộ chiếu và các thủ tục xuất nhập cảnh'}
            </p>
          </div>

          {/* Agent content — each tab renders independently */}
          <div className="transition-all duration-300">
            {activeTab === 'ticketing' && <SearchForm />}
            {activeTab === 'tour' && <TourAgent />}
            {activeTab === 'visa' && <VisaAgent />}
          </div>
        </div>
      </section>

      {/* Features section */}
      <section className="py-12 sm:py-16 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-xl sm:text-2xl font-bold text-center text-gray-800 mb-8">
            Dịch vụ của <span className="text-primary-600">ABTrip</span>
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
            {[
              {
                title: 'Đặt vé máy bay',
                desc: 'Tìm kiếm và đặt vé với giá tốt nhất',
                icon: '✈️',
                color: 'primary',
                tab: 'ticketing',
              },
              {
                title: 'Tour du lịch',
                desc: 'Khám phá các tour hấp dẫn trong và ngoài nước',
                icon: '🏖️',
                color: 'emerald',
                tab: 'tour',
              },
              {
                title: 'Visa & Hộ chiếu',
                desc: 'Hỗ trợ thủ tục xuất nhập cảnh toàn diện',
                icon: '🛂',
                color: 'violet',
                tab: 'visa',
              },
            ].map((sv) => (
              <button
                key={sv.tab}
                onClick={() => setActiveTab(sv.tab)}
                className="text-center p-6 card-hover cursor-pointer"
              >
                <div className="text-3xl mb-3">{sv.icon}</div>
                <h3 className="font-semibold text-gray-800 mb-1">{sv.title}</h3>
                <p className="text-gray-500 text-sm">{sv.desc}</p>
              </button>
            ))}
          </div>
        </div>
      </section>

      {/* Popular routes — only show for ticketing */}
      {activeTab === 'ticketing' && (
        <section className="py-12 sm:py-16 bg-gray-50">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <h2 className="text-xl sm:text-2xl font-bold text-center text-gray-800 mb-8">
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
      )}
    </div>
  );
}
