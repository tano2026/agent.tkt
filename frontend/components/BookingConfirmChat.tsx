'use client';

interface BookingConfirmChatProps {
  booking: {
    BookingCode?: string;
    BookingStatus?: string;
    AirlineCode?: string;
    FlightNumber?: string;
    DepartAirport?: string;
    ArrivalAirport?: string;
    DepartDate?: string;
    DepartTime?: string;
    ArrivalDate?: string;
    ArrivalTime?: string;
    AdultFare?: number;
    TotalFare?: number;
    Currency?: string;
    Passengers?: Array<{
      Title?: string;
      FirstName?: string;
      LastName?: string;
      Type?: string;
    }>;
    [key: string]: any;
  };
  onIssueTicket?: (code: string) => void;
  onCancel?: (code: string) => void;
}

const statusLabels: Record<string, { label: string; color: string }> = {
  CONFIRMED: { label: 'Đã xác nhận', color: 'text-green-600 bg-green-50 border-green-200' },
  PENDING: { label: 'Đang chờ', color: 'text-yellow-600 bg-yellow-50 border-yellow-200' },
  CANCELLED: { label: 'Đã hủy', color: 'text-red-600 bg-red-50 border-red-200' },
  ISSUED: { label: 'Đã xuất vé', color: 'text-blue-600 bg-blue-50 border-blue-200' },
};

export default function BookingConfirmChat({ booking, onIssueTicket, onCancel }: BookingConfirmChatProps) {
  const statusInfo = statusLabels[booking.BookingStatus || 'PENDING'] || statusLabels.PENDING;

  const formatCurrency = (amount?: number) => {
    if (!amount) return '0 ₫';
    return new Intl.NumberFormat('vi-VN', {
      style: 'currency',
      currency: booking.Currency || 'VND',
    }).format(amount);
  };

  return (
    <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden mb-2">
      {/* Success badge */}
      <div className="bg-green-50 px-4 py-3 text-center border-b border-green-100">
        <svg className="w-6 h-6 text-green-500 mx-auto mb-1" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
        </svg>
        <div className="text-sm font-bold text-green-700">Đặt vé thành công!</div>
      </div>

      {/* Booking code */}
      <div className="px-4 py-3 text-center border-b border-gray-50">
        <div className="text-[10px] text-gray-400 uppercase tracking-wider">Mã đặt chỗ</div>
        <div className="text-lg font-bold text-blue-700 tracking-widest mt-0.5">
          {booking.BookingCode || 'N/A'}
        </div>
        <span className={`inline-block mt-1 px-2.5 py-0.5 rounded-full text-[10px] font-medium border ${statusInfo.color}`}>
          {statusInfo.label}
        </span>
      </div>

      {/* Flight info */}
      <div className="px-4 py-2.5 border-b border-gray-50">
        <div className="flex items-center gap-2 mb-2">
          <div className="w-6 h-6 bg-blue-100 rounded-full flex items-center justify-center text-blue-700 font-bold text-[10px]">
            {booking.AirlineCode || ''}
          </div>
          <div className="text-xs font-medium">{booking.AirlineCode} {booking.FlightNumber}</div>
        </div>
        <div className="grid grid-cols-2 gap-2 text-[11px]">
          <div>
            <span className="text-gray-400">Đi:</span>
            <div className="font-medium text-gray-700">
              {booking.DepartAirport} → {booking.ArrivalAirport}
            </div>
          </div>
          <div>
            <span className="text-gray-400">Giờ:</span>
            <div className="font-medium text-gray-700">
              {booking.DepartDate} {booking.DepartTime}
            </div>
          </div>
        </div>
      </div>

      {/* Passengers */}
      {booking.Passengers && booking.Passengers.length > 0 && (
        <div className="px-4 py-2.5 border-b border-gray-50">
          <div className="text-[10px] text-gray-400 uppercase mb-1.5">Hành khách</div>
          {booking.Passengers.map((pax, i) => (
            <div key={i} className="text-[11px] text-gray-700">
              {pax.Title} {pax.FirstName} {pax.LastName}
              <span className="text-gray-400 ml-1">
                ({pax.Type === 'adult' ? 'NL' : pax.Type === 'child' ? 'TE' : 'EB'})
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Price */}
      <div className="px-4 py-2.5 border-b border-gray-50">
        <div className="flex justify-between text-xs">
          <span className="text-gray-400">Giá vé</span>
          <span className="font-medium">{formatCurrency(booking.AdultFare)}</span>
        </div>
        <div className="flex justify-between text-sm font-bold mt-1 pt-1.5 border-t border-gray-100">
          <span className="text-gray-700">Tổng cộng</span>
          <span className="text-blue-600">{formatCurrency(booking.TotalFare || booking.AdultFare)}</span>
        </div>
      </div>

      {/* Actions */}
      <div className="flex gap-2 px-4 py-2.5">
        {booking.BookingStatus !== 'ISSUED' && booking.BookingStatus !== 'CANCELLED' && (
          <>
            <button
              onClick={() => onIssueTicket?.(booking.BookingCode || '')}
              className="flex-1 text-[11px] font-medium py-1.5 rounded-lg bg-blue-500 text-white hover:bg-blue-600 transition-colors"
            >
              Xuất vé
            </button>
            <button
              onClick={() => onCancel?.(booking.BookingCode || '')}
              className="flex-1 text-[11px] font-medium py-1.5 rounded-lg border border-gray-300 text-gray-600 hover:bg-gray-50 transition-colors"
            >
              Hủy
            </button>
          </>
        )}
        {booking.BookingStatus === 'ISSUED' && (
          <div className="w-full text-center text-[11px] font-medium py-1.5 rounded-lg bg-blue-50 text-blue-600">
            ✓ Vé đã được xuất
          </div>
        )}
        {booking.BookingStatus === 'CANCELLED' && (
          <div className="w-full text-center text-[11px] font-medium py-1.5 rounded-lg bg-red-50 text-red-600">
            ✕ Đã hủy
          </div>
        )}
      </div>
    </div>
  );
}
