'use client';

import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import BookingConfirm from '@/components/BookingConfirm';

export default function BookingDetailPage() {
  const params = useParams();
  const code = params.code as string;

  const [booking, setBooking] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    try {
      // Try to load from sessionStorage first
      const stored = sessionStorage.getItem(`booking_${code}`);
      if (stored) {
        setBooking(JSON.parse(stored));
      } else {
        // Fallback: just show the code
        setBooking({ BookingCode: code, BookingStatus: 'PENDING' });
      }
    } catch {
      setBooking({ BookingCode: code, BookingStatus: 'PENDING' });
    } finally {
      setLoading(false);
    }
  }, [code]);

  if (loading) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-16 text-center">
        <div className="inline-block w-10 h-10 border-4 border-primary-200 border-t-primary-600 rounded-full animate-spin mb-4" />
        <p className="text-gray-500">Đang tải thông tin đặt vé...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-16 text-center">
        <div className="card p-8">
          <p className="text-gray-500">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-10">
      <BookingConfirm booking={booking} />
    </div>
  );
}
