'use client';

interface FlightCardChatProps {
  flight: {
    AirlineCode?: string;
    FlightNumber?: string;
    DepartAirport?: string;
    ArrivalAirport?: string;
    DepartTime?: string;
    ArrivalTime?: string;
    DepartDate?: string;
    ArrivalDate?: string;
    Duration?: string;
    FareClass?: string;
    AdultFare?: number;
    Currency?: string;
    AvailableSeats?: number;
    StopQuantity?: number;
    SessionCode?: string;
    [key: string]: any;
  };
  onSelect: (flight: any) => void;
}

const airlineNames: Record<string, string> = {
  VN: 'Vietnam Airlines',
  VJ: 'VietJet Air',
  QH: 'Bamboo Airways',
  BL: 'Pacific Airlines',
  VU: 'Vietravel Airlines',
};

const airlineColors: Record<string, string> = {
  VN: 'bg-green-500',
  VJ: 'bg-red-500',
  QH: 'bg-blue-500',
  BL: 'bg-orange-500',
  VU: 'bg-purple-500',
};

const airportNames: Record<string, string> = {
  HAN: 'Hà Nội',
  SGN: 'HCM',
  DAD: 'Đà Nẵng',
  CXR: 'Nha Trang',
  VII: 'Vinh',
  HUI: 'Huế',
  PQC: 'Phú Quốc',
};

export default function FlightCardChat({ flight, onSelect }: FlightCardChatProps) {
  const airline = flight.AirlineCode || 'N/A';
  const airlineName = airlineNames[airline] || airline;
  const airlineColor = airlineColors[airline] || 'bg-gray-500';

  const formatCurrency = (amount?: number) => {
    if (!amount) return '0 ₫';
    return new Intl.NumberFormat('vi-VN', {
      style: 'currency',
      currency: flight.Currency || 'VND',
    }).format(amount);
  };

  const formatTime = (time?: string) => {
    if (!time) return '--:--';
    return time.substring(0, 5);
  };

  const duration = flight.Duration || '--:--';
  const stops = flight.StopQuantity ?? 0;
  const seats = flight.AvailableSeats ?? 0;
  const fromCity = airportNames[flight.DepartAirport || ''] || flight.DepartAirport || '--';
  const toCity = airportNames[flight.ArrivalAirport || ''] || flight.ArrivalAirport || '--';

  return (
    <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden mb-2 hover:shadow-md transition-shadow">
      {/* Airline header */}
      <div className="flex items-center gap-2 px-3 py-2 bg-gray-50 border-b border-gray-100">
        <div className={`w-7 h-7 ${airlineColor} rounded-full flex items-center justify-center text-white font-bold text-[10px]`}>
          {airline}
        </div>
        <span className="text-xs font-medium text-gray-700">{airlineName}</span>
        <span className="text-[10px] text-gray-400 ml-auto">{flight.FlightNumber || ''}</span>
      </div>

      {/* Route & time */}
      <div className="px-3 py-2.5">
        <div className="flex items-center gap-2">
          <div className="text-center min-w-[60px]">
            <div className="text-base font-bold text-gray-900">{formatTime(flight.DepartTime)}</div>
            <div className="text-[10px] text-gray-500">{fromCity}</div>
            <div className="text-[10px] text-gray-400 font-mono">{flight.DepartAirport || ''}</div>
          </div>

          <div className="flex-1 flex flex-col items-center px-1">
            <div className="text-[10px] text-gray-400 mb-0.5">{duration}</div>
            <div className="relative w-full h-[2px] bg-gray-200">
              <div className="absolute top-1/2 -translate-y-1/2 left-0 w-1.5 h-1.5 bg-gray-300 rounded-full" />
              <div className="absolute top-1/2 -translate-y-1/2 right-0 w-1.5 h-1.5 bg-gray-300 rounded-full" />
            </div>
            <div className="text-[10px] text-gray-400 mt-0.5">
              {stops === 0 ? 'Bay thẳng' : `${stops} điểm dừng`}
            </div>
          </div>

          <div className="text-center min-w-[60px]">
            <div className="text-base font-bold text-gray-900">{formatTime(flight.ArrivalTime)}</div>
            <div className="text-[10px] text-gray-500">{toCity}</div>
            <div className="text-[10px] text-gray-400 font-mono">{flight.ArrivalAirport || ''}</div>
          </div>
        </div>
      </div>

      {/* Price + button */}
      <div className="flex items-center justify-between px-3 py-2 border-t border-gray-100 bg-gray-50/50">
        <div>
          <div className="text-[10px] text-gray-400">Giá từ</div>
          <div className="text-sm font-bold text-blue-600">
            {formatCurrency(flight.AdultFare)}
          </div>
          {seats > 0 && seats <= 5 && (
            <div className="text-[10px] text-orange-500 font-medium">Còn {seats} chỗ</div>
          )}
        </div>
        <button
          onClick={() => onSelect(flight)}
          disabled={seats === 0}
          className={`text-xs font-medium px-4 py-1.5 rounded-lg transition-colors ${
            seats === 0
              ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
              : 'bg-blue-500 text-white hover:bg-blue-600 active:bg-blue-700'
          }`}
        >
          {seats === 0 ? 'Hết vé' : 'Đặt ngay'}
        </button>
      </div>
    </div>
  );
}
