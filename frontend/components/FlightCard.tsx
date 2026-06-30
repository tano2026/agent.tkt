interface FlightCardProps {
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
  VN: 'bg-green-600',
  VJ: 'bg-red-500',
  QH: 'bg-blue-600',
  BL: 'bg-orange-500',
  VU: 'bg-purple-600',
};

export default function FlightCard({ flight, onSelect }: FlightCardProps) {
  const airline = flight.AirlineCode || 'N/A';
  const airlineName = airlineNames[airline] || airline;
  const airlineColor = airlineColors[airline] || 'bg-gray-600';

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('vi-VN', {
      style: 'currency',
      currency: flight.Currency || 'VND',
    }).format(amount || 0);
  };

  const formatTime = (time?: string) => {
    if (!time) return '--:--';
    return time.substring(0, 5);
  };

  const duration = flight.Duration || '--:--';
  const stops = flight.StopQuantity ?? 0;
  const seats = flight.AvailableSeats ?? 0;

  return (
    <div className="card-hover p-4 sm:p-5">
      <div className="flex flex-col sm:flex-row sm:items-center gap-4">
        {/* Airline info */}
        <div className="flex items-center gap-3 sm:w-48 shrink-0">
          <div className={`w-10 h-10 ${airlineColor} rounded-full flex items-center justify-center text-white font-bold text-sm`}>
            {airline}
          </div>
          <div>
            <div className="font-semibold text-sm">{airlineName}</div>
            <div className="text-xs text-gray-500">{flight.FlightNumber || '--'}</div>
          </div>
        </div>

        {/* Flight route & time */}
        <div className="flex-1 flex items-center gap-2 sm:gap-4">
          <div className="text-center min-w-[80px]">
            <div className="text-xl font-bold text-gray-900">{formatTime(flight.DepartTime)}</div>
            <div className="text-xs text-gray-500">{flight.DepartAirport || '--'}</div>
          </div>

          <div className="flex-1 flex flex-col items-center px-2">
            <div className="text-xs text-gray-400 mb-1">{duration}</div>
            <div className="relative w-full h-px bg-gray-300">
              <div className="absolute top-1/2 -translate-y-1/2 left-0 w-2 h-2 bg-gray-400 rounded-full" />
              <div className="absolute top-1/2 -translate-y-1/2 right-0 w-2 h-2 bg-gray-400 rounded-full" />
              <div className="absolute top-1/2 -translate-y-1/2 left-1/2 -translate-x-1/2">
                {stops > 0 ? (
                  <div className="w-3 h-3 bg-primary-500 rounded-full border-2 border-white" />
                ) : null}
              </div>
            </div>
            <div className="text-xs text-gray-400 mt-1">
              {stops === 0 ? 'Bay thẳng' : `${stops} điểm dừng`}
            </div>
          </div>

          <div className="text-center min-w-[80px]">
            <div className="text-xl font-bold text-gray-900">{formatTime(flight.ArrivalTime)}</div>
            <div className="text-xs text-gray-500">{flight.ArrivalAirport || '--'}</div>
          </div>
        </div>

        {/* Price & select */}
        <div className="flex sm:flex-col items-center sm:items-end justify-between sm:justify-center gap-2 sm:w-44 shrink-0 border-t sm:border-t-0 sm:border-l border-gray-100 pt-3 sm:pt-0 sm:pl-4">
          <div>
            <div className="text-sm text-gray-500">Giá từ</div>
            <div className="text-xl font-bold text-primary-600">
              {formatCurrency(flight.AdultFare || 0)}
            </div>
          </div>
          <button
            onClick={() => onSelect(flight)}
            disabled={seats === 0}
            className={`btn-primary text-sm py-2 px-6 ${
              seats === 0 ? 'opacity-50 cursor-not-allowed' : ''
            }`}
          >
            {seats === 0 ? 'Hết vé' : 'Chọn'}
          </button>
          {seats > 0 && seats <= 5 && (
            <div className="text-xs text-orange-500 font-medium">
              Chỉ còn {seats} chỗ
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
