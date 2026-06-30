'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { getAirports } from '@/lib/api';

interface Airport {
  AirportCode: string;
  AirportName: string;
  CityName: string;
}

interface SearchFormData {
  origin: string;
  destination: string;
  departDate: string;
  returnDate: string;
  adults: number;
  children: number;
  infants: number;
  cabinClass: string;
  tripType: string;
}

export default function SearchForm() {
  const router = useRouter();
  const [airports, setAirports] = useState<Airport[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [originSearch, setOriginSearch] = useState('');
  const [destSearch, setDestSearch] = useState('');
  const [showOriginDropdown, setShowOriginDropdown] = useState(false);
  const [showDestDropdown, setShowDestDropdown] = useState(false);
  const originRef = useRef<HTMLDivElement>(null);
  const destRef = useRef<HTMLDivElement>(null);

  const [formData, setFormData] = useState<SearchFormData>({
    origin: '',
    destination: '',
    departDate: '',
    returnDate: '',
    adults: 1,
    children: 0,
    infants: 0,
    cabinClass: 'economy',
    tripType: 'oneway',
  });

  useEffect(() => {
    const fetchAirports = async () => {
      try {
        const data = await getAirports();
        if (data.StatusCode === '000' && Array.isArray(data.Result)) {
          // Normalize: some airports may be strings, others objects
          const normalized: Airport[] = data.Result.map((item: any) => {
            if (typeof item === 'string') {
              // Try to parse "HAN - Ha Noi (Noi Bai)" format
              const match = item.match(/^(\w+)\s*-\s*(.+)/);
              if (match) {
                return {
                  AirportCode: match[1].trim(),
                  AirportName: match[2].trim(),
                  CityName: match[2].split('(')[0]?.trim() || match[2].trim(),
                };
              }
              return { AirportCode: item, AirportName: item, CityName: item };
            }
            return {
              AirportCode: item.AirportCode || item.airportCode || item.code || '',
              AirportName: item.AirportName || item.airportName || item.name || '',
              CityName: item.CityName || item.cityName || item.city || '',
            };
          });
          setAirports(normalized);
        }
      } catch (err) {
        // Fallback airports if API fails
        setAirports([
          { AirportCode: 'HAN', AirportName: 'Nội Bài', CityName: 'Hà Nội' },
          { AirportCode: 'SGN', AirportName: 'Tân Sơn Nhất', CityName: 'Hồ Chí Minh' },
          { AirportCode: 'DAD', AirportName: 'Đà Nẵng', CityName: 'Đà Nẵng' },
          { AirportCode: 'CXR', AirportName: 'Cam Ranh', CityName: 'Nha Trang' },
          { AirportCode: 'HUI', AirportName: 'Phú Bài', CityName: 'Huế' },
          { AirportCode: 'PQC', AirportName: 'Phú Quốc', CityName: 'Phú Quốc' },
          { AirportCode: 'HPH', AirportName: 'Cát Bi', CityName: 'Hải Phòng' },
          { AirportCode: 'VCA', AirportName: 'Trà Nóc', CityName: 'Cần Thơ' },
        ]);
      } finally {
        setLoading(false);
      }
    };
    fetchAirports();
  }, []);

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (originRef.current && !originRef.current.contains(e.target as Node)) {
        setShowOriginDropdown(false);
      }
      if (destRef.current && !destRef.current.contains(e.target as Node)) {
        setShowDestDropdown(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const filteredOrigins = airports.filter(
    (a) =>
      a.AirportCode.toLowerCase().includes(originSearch.toLowerCase()) ||
      a.CityName.toLowerCase().includes(originSearch.toLowerCase()) ||
      a.AirportName.toLowerCase().includes(originSearch.toLowerCase())
  );

  const filteredDests = airports.filter(
    (a) =>
      a.AirportCode.toLowerCase().includes(destSearch.toLowerCase()) ||
      a.CityName.toLowerCase().includes(destSearch.toLowerCase()) ||
      a.AirportName.toLowerCase().includes(destSearch.toLowerCase())
  );

  const selectOrigin = (airport: Airport) => {
    setFormData({ ...formData, origin: airport.AirportCode });
    setOriginSearch(`${airport.CityName} (${airport.AirportCode})`);
    setShowOriginDropdown(false);
  };

  const selectDest = (airport: Airport) => {
    setFormData({ ...formData, destination: airport.AirportCode });
    setDestSearch(`${airport.CityName} (${airport.AirportCode})`);
    setShowDestDropdown(false);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.origin || !formData.destination) {
      setError('Vui lòng chọn điểm đi và điểm đến');
      return;
    }
    if (formData.origin === formData.destination) {
      setError('Điểm đi và điểm đến không được trùng nhau');
      return;
    }
    if (!formData.departDate) {
      setError('Vui lòng chọn ngày đi');
      return;
    }
    setError('');

    const params = new URLSearchParams({
      origin: formData.origin,
      destination: formData.destination,
      departDate: formData.departDate.split('-').reverse().join(''),
      returnDate: formData.tripType === 'roundtrip' && formData.returnDate
        ? formData.returnDate.split('-').reverse().join('')
        : '',
      adults: String(formData.adults),
      children: String(formData.children),
      infants: String(formData.infants),
      cabinClass: formData.cabinClass,
      tripType: formData.tripType,
    });
    router.push(`/search?${params.toString()}`);
  };

  const updateField = (field: keyof SearchFormData, value: string | number) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    if (field === 'tripType' && value === 'oneway') {
      setFormData((prev) => ({ ...prev, tripType: 'oneway', returnDate: '' }));
    }
  };

  const today = new Date().toISOString().split('T')[0];

  return (
    <form onSubmit={handleSubmit} className="w-full max-w-4xl mx-auto">
      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm">
          {error}
        </div>
      )}

      {/* Trip type toggle */}
      <div className="flex gap-4 mb-4">
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="radio"
            name="tripType"
            value="oneway"
            checked={formData.tripType === 'oneway'}
            onChange={(e) => updateField('tripType', e.target.value)}
            className="accent-primary-600"
          />
          <span className="text-sm font-medium text-gray-700">Một chiều</span>
        </label>
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="radio"
            name="tripType"
            value="roundtrip"
            checked={formData.tripType === 'roundtrip'}
            onChange={(e) => updateField('tripType', e.target.value)}
            className="accent-primary-600"
          />
          <span className="text-sm font-medium text-gray-700">Khứ hồi</span>
        </label>
      </div>

      {/* Main search grid */}
      <div className="card p-4 sm:p-6 space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {/* Origin */}
          <div ref={originRef} className="relative">
            <label className="block text-sm font-medium text-gray-700 mb-1">Điểm đi</label>
            <input
              type="text"
              className="input-field"
              placeholder="Chọn thành phố..."
              value={originSearch}
              onChange={(e) => {
                setOriginSearch(e.target.value);
                setShowOriginDropdown(true);
                if (!e.target.value) setFormData((prev) => ({ ...prev, origin: '' }));
              }}
              onFocus={() => setShowOriginDropdown(true)}
            />
            {showOriginDropdown && (
              <div className="absolute z-10 mt-1 w-full bg-white border border-gray-200 rounded-lg shadow-lg max-h-60 overflow-y-auto">
                {loading ? (
                  <div className="p-3 text-sm text-gray-500">Đang tải...</div>
                ) : filteredOrigins.length === 0 ? (
                  <div className="p-3 text-sm text-gray-500">Không tìm thấy sân bay</div>
                ) : (
                  filteredOrigins.map((airport) => (
                    <button
                      key={airport.AirportCode}
                      type="button"
                      className="w-full text-left px-4 py-2.5 hover:bg-primary-50 text-sm transition-colors"
                      onClick={() => selectOrigin(airport)}
                    >
                      <span className="font-medium">{airport.CityName}</span>
                      <span className="text-gray-400 ml-2">({airport.AirportCode})</span>
                      <span className="text-gray-400 ml-2 text-xs">{airport.AirportName}</span>
                    </button>
                  ))
                )}
              </div>
            )}
          </div>

          {/* Destination */}
          <div ref={destRef} className="relative">
            <label className="block text-sm font-medium text-gray-700 mb-1">Điểm đến</label>
            <input
              type="text"
              className="input-field"
              placeholder="Chọn thành phố..."
              value={destSearch}
              onChange={(e) => {
                setDestSearch(e.target.value);
                setShowDestDropdown(true);
                if (!e.target.value) setFormData((prev) => ({ ...prev, destination: '' }));
              }}
              onFocus={() => setShowDestDropdown(true)}
            />
            {showDestDropdown && (
              <div className="absolute z-10 mt-1 w-full bg-white border border-gray-200 rounded-lg shadow-lg max-h-60 overflow-y-auto">
                {loading ? (
                  <div className="p-3 text-sm text-gray-500">Đang tải...</div>
                ) : filteredDests.length === 0 ? (
                  <div className="p-3 text-sm text-gray-500">Không tìm thấy sân bay</div>
                ) : (
                  filteredDests.map((airport) => (
                    <button
                      key={airport.AirportCode}
                      type="button"
                      className="w-full text-left px-4 py-2.5 hover:bg-primary-50 text-sm transition-colors"
                      onClick={() => selectDest(airport)}
                    >
                      <span className="font-medium">{airport.CityName}</span>
                      <span className="text-gray-400 ml-2">({airport.AirportCode})</span>
                      <span className="text-gray-400 ml-2 text-xs">{airport.AirportName}</span>
                    </button>
                  ))
                )}
              </div>
            )}
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {/* Depart date */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Ngày đi</label>
            <input
              type="date"
              className="input-field"
              value={formData.departDate}
              min={today}
              onChange={(e) => updateField('departDate', e.target.value)}
              required
            />
          </div>

          {/* Return date */}
          {formData.tripType === 'roundtrip' && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Ngày về</label>
              <input
                type="date"
                className="input-field"
                value={formData.returnDate}
                min={formData.departDate || today}
                onChange={(e) => updateField('returnDate', e.target.value)}
              />
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
          {/* Adults */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Người lớn</label>
            <select
              className="input-field"
              value={formData.adults}
              onChange={(e) => updateField('adults', parseInt(e.target.value))}
            >
              {[1, 2, 3, 4, 5, 6].map((n) => (
                <option key={n} value={n}>{n}</option>
              ))}
            </select>
          </div>

          {/* Children */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Trẻ em</label>
            <select
              className="input-field"
              value={formData.children}
              onChange={(e) => updateField('children', parseInt(e.target.value))}
            >
              {[0, 1, 2, 3, 4].map((n) => (
                <option key={n} value={n}>{n}</option>
              ))}
            </select>
          </div>

          {/* Infants */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Em bé</label>
            <select
              className="input-field"
              value={formData.infants}
              onChange={(e) => updateField('infants', parseInt(e.target.value))}
            >
              {[0, 1, 2].map((n) => (
                <option key={n} value={n}>{n}</option>
              ))}
            </select>
          </div>

          {/* Cabin class */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Hạng vé</label>
            <select
              className="input-field"
              value={formData.cabinClass}
              onChange={(e) => updateField('cabinClass', e.target.value)}
            >
              <option value="economy">Phổ thông</option>
              <option value="premium">Phổ thông đặc biệt</option>
              <option value="business">Thương gia</option>
              <option value="first">Hạng nhất</option>
            </select>
          </div>
        </div>

        <button type="submit" className="btn-primary w-full sm:w-auto sm:px-12 py-3 text-base">
          Tìm chuyến bay
        </button>
      </div>
    </form>
  );
}
