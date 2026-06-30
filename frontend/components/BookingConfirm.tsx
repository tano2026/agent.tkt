interface BookingDetails {
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
}

interface BookingConfirmProps {
  booking: BookingDetails;
}

const statusLabels: Record<string, { label: string; color: string }> = {
  CONFIRMED: { label: 'Đã xác nhận', color: 'text-green-700 bg-green-50 border-green-200' },
  PENDING: { label: 'Đang chờ', color: 'text-yellow-700 bg-yellow-50 border-yellow-200' },
  CANCELLED: { label: 'Đã hủy', color: 'text-red-700 bg-red-50 border-red-200' },
  ISSUED: { label: 'Đã xuất vé', color: 'text-blue-700 bg-blue-50 border-blue-200' },
};

export default function BookingConfirm({ booking }: BookingConfirmProps) {
  const statusInfo = statusLabels[booking.BookingStatus || 'PENDING'] || statusLabels.PENDING;

  const formatCurrency = (amount?: number) => {
    if (!amount) return '0 ₫';
    return new Intl.NumberFormat('vi-VN', {
      style: 'currency',
      currency: booking.Currency || 'VND',
    }).format(amount);
  };

  return (
    <div className="space-y-6">
      {/* Success header */}
      <div className="card p-6 sm:p-8 text-center border-green-200 bg-green-50">
        <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <svg className="w-8 h-8 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
          </svg>
        </div>
        <h2 className="text-2xl font-bold text-green-800 mb-2">Đặt vé thành công!</h2>
        <p className="text-green-600">Mã đặt chỗ của bạn đã được ghi nhận</p>
      </div>

      {/* Booking code */}
      <div className="card p-6 text-center">
        <p className="text-sm text-gray-500 mb-1">Mã đặt chỗ</p>
        <p className="text-3xl font-bold text-primary-700 tracking-widest">
          {booking.BookingCode || 'N/A'}
        </p>
        <div className={`inline-flex mt-3 px-4 py-1.5 rounded-full text-sm font-medium border ${statusInfo.color}`}>
          {statusInfo.label}
        </div>
      </div>

      {/* Flight details */}
      <div className="card p-4 sm:p-6">
        <h3 className="font-semibold text-gray-800 text-lg mb-4">Chi tiết chuyến bay</h3>
        <div className="space-y-3">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-primary-100 rounded-full flex items-center justify-center text-primary-700 font-bold text-sm">
              {booking.AirlineCode || '--'}
            </div>
            <div>
              <div className="font-medium">{booking.AirlineCode} {booking.FlightNumber}</div>
              <div className="text-sm text-gray-500">
                {booking.DepartAirport} → {booking.ArrivalAirport}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-gray-500">Khởi hành:</span>
              <div className="font-medium">
                {booking.DepartDate} {booking.DepartTime}
              </div>
            </div>
            <div>
              <span className="text-gray-500">Đến nơi:</span>
              <div className="font-medium">
                {booking.ArrivalDate} {booking.ArrivalTime}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Passenger details */}
      {booking.Passengers && booking.Passengers.length > 0 && (
        <div className="card p-4 sm:p-6">
          <h3 className="font-semibold text-gray-800 text-lg mb-4">Thông tin hành khách</h3>
          <div className="divide-y divide-gray-100">
            {booking.Passengers.map((pax, index) => (
              <div key={index} className="py-3 flex items-center gap-3">
                <div className="w-8 h-8 bg-gray-100 rounded-full flex items-center justify-center text-gray-600 text-sm font-medium">
                  {index + 1}
                </div>
                <div>
                  <div className="font-medium">
                    {pax.Title} {pax.FirstName} {pax.LastName}
                  </div>
                  <div className="text-sm text-gray-500">
                    {pax.Type === 'adult' ? 'Người lớn' : pax.Type === 'child' ? 'Trẻ em' : 'Em bé'}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Price summary */}
      <div className="card p-4 sm:p-6">
        <h3 className="font-semibold text-gray-800 text-lg mb-4">Chi tiết giá vé</h3>
        <div className="space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-gray-500">Giá vé người lớn</span>
            <span className="font-medium">{formatCurrency(booking.AdultFare)}</span>
          </div>
          <div className="border-t border-gray-100 pt-2 flex justify-between text-base">
            <span className="font-semibold">Tổng cộng</span>
            <span className="font-bold text-primary-600 text-lg">{formatCurrency(booking.TotalFare)}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
