'use client';

import { useState, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import FlightCard from '@/components/FlightCard';
import { searchFlights } from '@/lib/api';

interface Flight {
  AirlineCode?: string;
  FlightNumber?: string;
  DepartAirport?: string;
  ArrivalAirport?: string;
  DepartTime?: string;
  ArrivalTime?: string;
  DepartDate?: string;
  ArrivalDate?: string;
  Duration?: string;
  AdultFare?: number;
  Currency?: string;
  AvailableSeats?: number;
  [key: string]: any;
}

export default function SearchClient() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [flights, setFlights] = useState<Flight[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [sortBy, setSortBy] = useState<'price' | 'time' | 'duration'>('price');

  const origin = searchParams.get('origin') || '';
  const destination = searchParams.get('destination') || '';
  const departDate = searchParams.get('departDate') || '';
  const returnDate = searchParams.get('returnDate') || '';
  const adults = parseInt(searchParams.get('adults') || '1');
  const children = parseInt(searchParams.get('children') || '0');
  const infants = parseInt(searchParams.get('infants') || '0');
  const cabinClass = searchParams.get('cabinClass') || 'economy';
  const tripType = searchParams.get('tripType') || 'oneway';

  useEffect(() => {
    if (!origin || !destination || !departDate) {
      setError('Vui lòng nhập đầy đủ thông tin tìm kiếm');
      setLoading(false);
      return;
    }

    const fetchFlights = async () => {
      setLoading(true);
      setError('');
      try {
        const data = await searchFlights({
          origin,
          destination,
          departDate,
          returnDate: returnDate || undefined,
          adults,
          children,
          infants,
          cabinClass,
        });

        if (data.StatusCode === '000') {
          const result = data.Result || [];
          const flightList = Array.isArray(result) ? result : result.Flights || result.Itineraries || [];
          setFlights(flightList);
        } else {
          setError(data.Message || 'Không tìm thấy chuyến bay phù hợp');
          setFlights([]);
        }
      } catch (err: any) {
        setError(err.message || 'Có lỗi xảy ra khi tìm kiếm chuyến bay');
        setFlights([]);
      } finally {
        setLoading(false);
      }
    };

    fetchFlights();
  }, [origin, destination, departDate, returnDate, adults, children, infants, cabinClass]);

  const sortedFlights = [...flights].sort((a, b) => {
    if (sortBy === 'price') return (a.AdultFare || 0) - (b.AdultFare || 0);
    if (sortBy === 'time') return (a.DepartTime || '').localeCompare(b.DepartTime || '');
    if (sortBy === 'duration') return (a.Duration || '').localeCompare(b.Duration || '');
    return 0;
  });

  const handleSelectFlight = (flight: Flight) => {
    const sessionData = {
      flight,
      searchParams: {
        origin, destination, departDate, returnDate,
        adults, children, infants, cabinClass, tripType,
      },
    };
    // Store flight data in sessionStorage
    const sessionKey = `session_${Date.now()}`;
    sessionStorage.setItem(sessionKey, JSON.stringify(sessionData));
    router.push(`/book/${sessionKey}`);
  };

  const formatDate = (d: string) => {
    if (!d || d.length !== 8) return d;
    return `${d.substring(0, 2)}/${d.substring(2, 4)}/${d.substring(4, 8)}`;
  };

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-10">
      {/* Search summary */}
      <div className="card p-4 sm:p-6 mb-6">
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <span className="font-semibold text-gray-800">
            {origin} → {destination}
          </span>
          <span className="text-gray-400">|</span>
          <span className="text-gray-600">{formatDate(departDate)}</span>
          {tripType === 'roundtrip' && returnDate && (
            <>
              <span className="text-gray-400">-</span>
              <span className="text-gray-600">{formatDate(returnDate)}</span>
            </>
          )}
          <span className="text-gray-400">|</span>
          <span className="text-gray-600">
            {adults + children + infants} khách
          </span>
          <span className="text-gray-400">|</span>
          <span className="text-gray-600">
            {cabinClass === 'economy' ? 'Phổ thông' : cabinClass === 'business' ? 'Thương gia' : cabinClass}
          </span>
        </div>
      </div>

      {/* Sort controls */}
      {flights.length > 0 && (
        <div className="flex items-center gap-3 mb-4">
          <span className="text-sm text-gray-500">Sắp xếp:</span>
          {[
            { key: 'price', label: 'Giá thấp nhất' },
            { key: 'time', label: 'Giờ bay' },
            { key: 'duration', label: 'Thời gian bay' },
          ].map((opt) => (
            <button
              key={opt.key}
              onClick={() => setSortBy(opt.key as any)}
              className={`text-sm px-3 py-1.5 rounded-full transition-colors ${
                sortBy === opt.key
                  ? 'bg-primary-100 text-primary-700 font-medium'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="text-center py-16">
          <div className="inline-block w-10 h-10 border-4 border-primary-200 border-t-primary-600 rounded-full animate-spin mb-4" />
          <p className="text-gray-500">Đang tìm kiếm chuyến bay...</p>
        </div>
      )}

      {/* Error */}
      {error && !loading && (
        <div className="card p-8 text-center">
          <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg className="w-8 h-8 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>
          <h3 className="font-semibold text-gray-700 mb-2">Không tìm thấy chuyến bay</h3>
          <p className="text-gray-500 text-sm">{error}</p>
          <button
            onClick={() => router.push('/')}
            className="btn-secondary mt-4"
          >
            Quay lại tìm kiếm
          </button>
        </div>
      )}

      {/* Flight results */}
      {!loading && !error && flights.length === 0 && (
        <div className="card p-8 text-center">
          <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg className="w-8 h-8 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <p className="text-gray-500">Không có chuyến bay nào phù hợp với tìm kiếm của bạn</p>
        </div>
      )}

      {/* Results */}
      {!loading && flights.length > 0 && (
        <div className="space-y-3">
          <p className="text-sm text-gray-500 mb-2">
            Tìm thấy <span className="font-medium text-gray-700">{flights.length}</span> chuyến bay
          </p>
          {sortedFlights.map((flight, index) => (
            <FlightCard
              key={`${flight.AirlineCode}-${flight.FlightNumber}-${index}`}
              flight={flight}
              onSelect={handleSelectFlight}
            />
          ))}
        </div>
      )}
    </div>
  );
}
