'use client';

import { useState } from 'react';

export default function TourAgent() {
  const [destination, setDestination] = useState('');
  const [departDate, setDepartDate] = useState('');
  const [duration, setDuration] = useState('');
  const [travelers, setTravelers] = useState(2);

  const today = new Date().toISOString().split('T')[0];

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    alert('🔧 Tour Agent đang phát triển — tính năng sẽ sớm ra mắt!');
  };

  return (
    <div className="w-full max-w-4xl mx-auto">
      {/* Header */}
      <div className="text-center mb-8">
        <div className="inline-flex items-center justify-center w-16 h-16 bg-emerald-100 rounded-2xl mb-4">
          <svg className="w-8 h-8 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5" />
          </svg>
        </div>
        <h2 className="text-2xl font-bold text-gray-800 mb-2">Tour & Du lịch</h2>
        <p className="text-gray-500">Khám phá những tour du lịch hấp dẫn với giá tốt nhất</p>
      </div>

      <form onSubmit={handleSubmit} className="card p-6 space-y-4">
        {/* Destination */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Điểm đến</label>
          <input
            type="text"
            className="input-field"
            placeholder="Nhập điểm đến mong muốn..."
            value={destination}
            onChange={(e) => setDestination(e.target.value)}
          />
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {/* Depart date */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Ngày khởi hành</label>
            <input
              type="date"
              className="input-field"
              value={departDate}
              min={today}
              onChange={(e) => setDepartDate(e.target.value)}
            />
          </div>

          {/* Duration */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Thời gian</label>
            <select
              className="input-field"
              value={duration}
              onChange={(e) => setDuration(e.target.value)}
            >
              <option value="">Chọn thời gian</option>
              <option value="1-3">1 - 3 ngày</option>
              <option value="4-7">4 - 7 ngày</option>
              <option value="8-14">8 - 14 ngày</option>
              <option value="15+">Trên 14 ngày</option>
            </select>
          </div>

          {/* Travelers */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Số khách</label>
            <select
              className="input-field"
              value={travelers}
              onChange={(e) => setTravelers(parseInt(e.target.value))}
            >
              {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((n) => (
                <option key={n} value={n}>{n} khách</option>
              ))}
            </select>
          </div>
        </div>

        <button type="submit" className="btn-primary w-full sm:w-auto sm:px-12 py-3 text-base">
          Tìm tour
        </button>
      </form>

      {/* Coming soon features */}
      <div className="mt-8 grid grid-cols-1 sm:grid-cols-3 gap-4">
        {[
          { title: 'Tour trong nước', desc: 'Khám phá mọi miền đất nước', icon: '🏔️' },
          { title: 'Tour nước ngoài', desc: 'Du lịch quốc tế giá tốt', icon: '🌏' },
          { title: 'Tour combo', desc: 'Vé + Khách sạn tiết kiệm', icon: '🎯' },
        ].map((item) => (
          <div key={item.title} className="card p-4 text-center opacity-60">
            <div className="text-2xl mb-2">{item.icon}</div>
            <div className="font-medium text-gray-800 text-sm">{item.title}</div>
            <div className="text-xs text-gray-400 mt-1">{item.desc}</div>
            <div className="mt-2 text-xs text-emerald-500 font-medium">Sắp ra mắt →</div>
          </div>
        ))}
      </div>
    </div>
  );
}
