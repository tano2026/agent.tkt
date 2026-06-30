const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8765';

interface ApiRequest {
  PrivateKey: string;
  ApiAccount: string;
  ApiPassword: string;
  [key: string]: any;
}

interface ApiResponse {
  StatusCode?: string;
  Success?: boolean;
  Message?: string;
  Result?: any;
  [key: string]: any;
}

const DEFAULT_AUTH: Pick<ApiRequest, 'PrivateKey' | 'ApiAccount' | 'ApiPassword'> = {
  PrivateKey: process.env.NEXT_PUBLIC_PRIVATE_KEY || '3c091b43-8d4f-4f09-bf63-5f5347c24123',
  ApiAccount: process.env.NEXT_PUBLIC_API_ACCOUNT || 'tulike30',
  ApiPassword: process.env.NEXT_PUBLIC_API_PASSWORD || 'Tulike123@',
};

async function callApi(action: string, params: Record<string, any> = {}): Promise<ApiResponse> {
  const body: ApiRequest = {
    ...DEFAULT_AUTH,
    Action: action,
    ...params,
  };

  const response = await fetch(`${BACKEND_URL}/api`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get list of airports
 */
export async function getAirports(): Promise<ApiResponse> {
  return callApi('GetAirports');
}

/**
 * Get list of airlines
 */
export async function getAirlines(): Promise<ApiResponse> {
  return callApi('GetAirlines');
}

/**
 * Search for flights
 */
export async function searchFlights(params: {
  origin: string;
  destination: string;
  departDate: string; // DDMMYYYY
  returnDate?: string; // DDMMYYYY
  adults: number;
  children?: number;
  infants?: number;
  cabinClass?: string;
}): Promise<ApiResponse> {
  return callApi('SearchFlight', {
    DepartAirport: params.origin,
    ArrivalAirport: params.destination,
    DepartDate: params.departDate,
    ReturnDate: params.returnDate || '',
    Adult: params.adults,
    Children: params.children || 0,
    Infant: params.infants || 0,
    CabinClass: params.cabinClass || 'economy',
  });
}

/**
 * Book a flight
 */
export async function bookFlight(params: {
  sessionCode: string;
  passengers: Array<{
    title: string;
    lastName: string;
    firstName: string;
    gender: string;
    birthDate: string; // DDMMYYYY
    passportNumber?: string;
    passportExpiry?: string; // DDMMYYYY
    nationality?: string;
    type: 'adult' | 'child' | 'infant';
  }>;
}): Promise<ApiResponse> {
  return callApi('BookFlight', {
    SessionCode: params.sessionCode,
    Passengers: params.passengers.map((p) => ({
      Title: p.title,
      LastName: p.lastName,
      FirstName: p.firstName,
      Gender: p.gender,
      BirthDate: p.birthDate,
      PassportNumber: p.passportNumber || '',
      PassportExpiry: p.passportExpiry || '',
      Nationality: p.nationality || 'VN',
      Type: p.type,
    })),
  });
}

/**
 * Issue tickets for a booking
 */
export async function issueTicket(bookingCode: string): Promise<ApiResponse> {
  return callApi('IssueTicket', {
    BookingCode: bookingCode,
  });
}

/**
 * Get booking details by code
 */
export async function getBookingDetail(bookingCode: string): Promise<ApiResponse> {
  return callApi('BookingDetail', {
    BookingCode: bookingCode,
  });
}

export type { ApiRequest, ApiResponse };
