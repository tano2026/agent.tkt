'use client';

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import BookingForm from '@/components/BookingForm';
import { bookFlight } from '@/lib/api';

interface PassengerData {
  title: string;
  lastName: string;
  firstName: string;
  gender: string;
  birthDate: string;
  passportNumber: string;
  passportExpiry: string;
  nationality: string;
  type: 'adult' | 'child' | 'infant';
}

interface FlightInfo {
  AirlineCode?: string;
  FlightNumber?: string;
  DepartAirport?: string;
  ArrivalAirport?: string;
  DepartTime?: string;
  ArrivalTime?: string;
  DepartDate?: string;
  ArrivalDate?: string;
  AdultFare?: number;
  Currency?: string;
  [key: string]: any;
}

export default function BookClient() {
  const params = useParams();
  const router = useRouter();
  const session = params.session as string;

  const [flightInfo, setFlightInfo] = useState<FlightInfo | null>(null);
  const [passengerCount, setPassengerCount] = useState({ adults: 1, children: 0, infants: 0 });
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    try {
      const data = sessionStorage.getItem(session);
      if (!data) {
        setError('Phiên đặt vé đã hết hạn. Vui lòng tìm kiếm lại.');
        setLoading(false);
        return;
      }
      const parsed = JSON.parse(data);
      setFlightInfo(parsed.flight);
      setPassengerCount({
        adults: parsed.searchParams?.adults || 1,
        children: parsed.searchParams?.children || 0,
        infants: parsed.searchParams?.infants || 0,
      });
    } catch {
      setError('Dữ liệu không hợp lệ');
    } finally {
      setLoading(false);
    }
  }, [session]);

  const handleSubmit = async (passengers: PassengerData[]) => {
    setSubmitting(true);
    setError('');

    try {
      // Convert date from YYYY-MM-DD to DDMMYYYY
      const toDDMMYYYY = (dateStr: string) => {
        if (!dateStr) return '';
        const parts = dateStr.split('-');
        if (parts.length === 3) return `${parts[2]}${parts[1]}${parts[0]}`;
        return dateStr;
      };

      // Call bookFlight API
      const result = await bookFlight({
        sessionCode: session,
        passengers: passengers.map((p) => ({
          ...p,
          birthDate: toDDMMYYYY(p.birthDate),
          passportExpiry: p.passportExpiry ? toDDMMYYYY(p.passportExpiry) : '',
        })),
      });

      if (result.StatusCode === '000' || result.Success) {
        const bookingCode = result.BookingCode || result.Result?.BookingCode || result.Result?.bookingCode || '';
        // Store booking result
        sessionStorage.setItem(`booking_${bookingCode}`, JSON.stringify(result.Result || result));
        router.push(`/booking/${bookingCode}`);
      } else {
        setError(result.Message || 'Đặt vé không thành công. Vui lòng thử lại.');
      }
    } catch (err: any) {
      setError(err.message || 'Có lỗi xảy ra khi đặt vé');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-16 text-center">
        <div className="inline-block w-10 h-10 border-4 border-primary-200 border-t-primary-600 rounded-full animate-spin mb-4" />
        <p className="text-gray-500">Đang tải thông tin...</p>
      </div>
    );
  }

  if (error && !flightInfo) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-16 text-center">
        <div className="card p-8">
          <h2 className="font-semibold text-gray-700 mb-2">Không thể tiếp tục</h2>
          <p className="text-gray-500 text-sm mb-4">{error}</p>
          <button onClick={() => router.push('/')} className="btn-primary">
            Quay lại trang chủ
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-10">
      <h1 className="text-2xl font-bold text-gray-800 mb-6">Thông tin hành khách</h1>

      <BookingForm
        passengerCount={passengerCount}
        flightInfo={flightInfo}
        sessionCode={session}
        onSubmit={handleSubmit}
        submitting={submitting}
        error={error}
      />
    </div>
  );
}
