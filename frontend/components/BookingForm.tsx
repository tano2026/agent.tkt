'use client';

import { useState } from 'react';

interface Passenger {
  type: 'adult' | 'child' | 'infant';
  title: string;
  lastName: string;
  firstName: string;
  gender: string;
  birthDate: string;
  passportNumber: string;
  passportExpiry: string;
  nationality: string;
}

interface BookingFormProps {
  passengerCount: { adults: number; children: number; infants: number };
  flightInfo: any;
  sessionCode: string;
  onSubmit: (passengers: Passenger[]) => void;
  submitting: boolean;
  error: string;
}

const TITLE_OPTIONS = ['Mr', 'Mrs', 'Ms', 'Dr'];

export default function BookingForm({
  passengerCount,
  flightInfo,
  sessionCode,
  onSubmit,
  submitting,
  error,
}: BookingFormProps) {
  const [passengers, setPassengers] = useState<Passenger[]>(() => {
    const list: Passenger[] = [];
    for (let i = 0; i < passengerCount.adults; i++) {
      list.push({
        type: 'adult',
        title: 'Mr',
        lastName: '',
        firstName: '',
        gender: 'male',
        birthDate: '',
        passportNumber: '',
        passportExpiry: '',
        nationality: 'VN',
      });
    }
    for (let i = 0; i < passengerCount.children; i++) {
      list.push({
        type: 'child',
        title: 'Mr',
        lastName: '',
        firstName: '',
        gender: 'male',
        birthDate: '',
        passportNumber: '',
        passportExpiry: '',
        nationality: 'VN',
      });
    }
    for (let i = 0; i < passengerCount.infants; i++) {
      list.push({
        type: 'infant',
        title: 'Mr',
        lastName: '',
        firstName: '',
        gender: 'male',
        birthDate: '',
        passportNumber: '',
        passportExpiry: '',
        nationality: 'VN',
      });
    }
    return list;
  });

  const typeLabels: Record<string, string> = {
    adult: 'Người lớn',
    child: 'Trẻ em',
    infant: 'Em bé',
  };

  const updatePassenger = (index: number, field: keyof Passenger, value: string) => {
    setPassengers((prev) => {
      const updated = [...prev];
      updated[index] = { ...updated[index], [field]: value };
      return updated;
    });
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    // Basic validation
    for (let i = 0; i < passengers.length; i++) {
      const p = passengers[i];
      if (!p.lastName.trim() || !p.firstName.trim()) {
        alert(`Vui lòng nhập họ và tên cho hành khách ${i + 1}`);
        return;
      }
      if (!p.birthDate) {
        alert(`Vui lòng nhập ngày sinh cho hành khách ${i + 1}`);
        return;
      }
    }

    onSubmit(passengers);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {error && (
        <div className="p-4 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm">
          {error}
        </div>
      )}

      {/* Flight summary */}
      {flightInfo && (
        <div className="card p-4 bg-primary-50 border-primary-100">
          <h3 className="font-semibold text-primary-800 mb-2">Thông tin chuyến bay</h3>
          <div className="text-sm text-primary-700 space-y-1">
            <p>
              <span className="font-medium">{flightInfo.AirlineCode}</span> {flightInfo.FlightNumber} &middot;{' '}
              {flightInfo.DepartAirport} → {flightInfo.ArrivalAirport}
            </p>
            <p>
              {flightInfo.DepartDate} {flightInfo.DepartTime} - {flightInfo.ArrivalDate} {flightInfo.ArrivalTime}
            </p>
          </div>
        </div>
      )}

      {/* Passenger forms */}
      {passengers.map((passenger, index) => (
        <div key={index} className="card p-4 sm:p-6">
          <h3 className="font-semibold text-gray-800 text-lg mb-4">
            Hành khách {index + 1} - {typeLabels[passenger.type]}
          </h3>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {/* Title */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Danh xưng</label>
              <select
                className="input-field"
                value={passenger.title}
                onChange={(e) => updatePassenger(index, 'title', e.target.value)}
              >
                {TITLE_OPTIONS.map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </div>

            {/* Last name */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Họ</label>
              <input
                type="text"
                className="input-field"
                placeholder="Nguyễn"
                value={passenger.lastName}
                onChange={(e) => updatePassenger(index, 'lastName', e.target.value)}
                required
              />
            </div>

            {/* First name */}
            <div className="sm:col-span-1">
              <label className="block text-sm font-medium text-gray-700 mb-1">Tên</label>
              <input
                type="text"
                className="input-field"
                placeholder="Văn A"
                value={passenger.firstName}
                onChange={(e) => updatePassenger(index, 'firstName', e.target.value)}
                required
              />
            </div>

            {/* Gender */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Giới tính</label>
              <select
                className="input-field"
                value={passenger.gender}
                onChange={(e) => updatePassenger(index, 'gender', e.target.value)}
              >
                <option value="male">Nam</option>
                <option value="female">Nữ</option>
                <option value="other">Khác</option>
              </select>
            </div>

            {/* Birth date */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Ngày sinh</label>
              <input
                type="date"
                className="input-field"
                value={passenger.birthDate}
                onChange={(e) => updatePassenger(index, 'birthDate', e.target.value)}
                required
              />
            </div>

            {/* Nationality */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Quốc tịch</label>
              <select
                className="input-field"
                value={passenger.nationality}
                onChange={(e) => updatePassenger(index, 'nationality', e.target.value)}
              >
                <option value="VN">Việt Nam</option>
                <option value="US">Hoa Kỳ</option>
                <option value="GB">Vương quốc Anh</option>
                <option value="JP">Nhật Bản</option>
                <option value="KR">Hàn Quốc</option>
                <option value="CN">Trung Quốc</option>
                <option value="FR">Pháp</option>
                <option value="DE">Đức</option>
                <option value="AU">Úc</option>
                <option value="SG">Singapore</option>
                <option value="TH">Thái Lan</option>
                <option value="MY">Malaysia</option>
              </select>
            </div>

            {/* Passport number */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Số hộ chiếu</label>
              <input
                type="text"
                className="input-field"
                placeholder="C1234567"
                value={passenger.passportNumber}
                onChange={(e) => updatePassenger(index, 'passportNumber', e.target.value)}
              />
            </div>

            {/* Passport expiry */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Ngày hết hạn hộ chiếu</label>
              <input
                type="date"
                className="input-field"
                value={passenger.passportExpiry}
                onChange={(e) => updatePassenger(index, 'passportExpiry', e.target.value)}
              />
            </div>
          </div>
        </div>
      ))}

      {/* Submit */}
      <div className="flex flex-col sm:flex-row justify-between items-center gap-4 pt-2">
        <p className="text-sm text-gray-500">
          Vui lòng kiểm tra kỹ thông tin hành khách trước khi đặt vé
        </p>
        <button
          type="submit"
          disabled={submitting}
          className="btn-primary px-10 py-3 text-base disabled:opacity-50"
        >
          {submitting ? 'Đang xử lý...' : 'Xác nhận đặt vé'}
        </button>
      </div>
    </form>
  );
}
