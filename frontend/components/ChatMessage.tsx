'use client';

import FlightCardChat from '@/components/FlightCardChat';
import BookingConfirmChat from '@/components/BookingConfirmChat';

export interface ChatMessageData {
  id: string;
  type: 'user' | 'bot' | 'flight-results' | 'booking-confirm' | 'error' | 'loading';
  text?: string;
  flights?: any[];
  booking?: any;
  onSelectFlight?: (flight: any) => void;
  onIssueTicket?: (code: string) => void;
  onCancelBooking?: (code: string) => void;
}

interface ChatMessageProps {
  message: ChatMessageData;
}

export default function ChatMessage({ message }: ChatMessageProps) {
  // Loading indicator (typing dots)
  if (message.type === 'loading') {
    return (
      <div className="flex justify-start px-4 py-1.5 animate-fade-in">
        <div className="bg-white border border-gray-100 rounded-2xl rounded-bl-sm px-4 py-3 shadow-sm">
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
            <span className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
            <span className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
          </div>
        </div>
      </div>
    );
  }

  // User message
  if (message.type === 'user') {
    return (
      <div className="flex justify-end px-4 py-1.5 animate-slide-in-right">
        <div className="max-w-[85%] sm:max-w-[75%] bg-blue-500 text-white rounded-2xl rounded-br-sm px-4 py-2.5 shadow-sm">
          <p className="text-sm leading-relaxed whitespace-pre-wrap">{message.text}</p>
        </div>
      </div>
    );
  }

  // Bot text message
  if (message.type === 'bot') {
    return (
      <div className="flex justify-start px-4 py-1.5 animate-slide-in-left">
        <div className="max-w-[85%] sm:max-w-[75%] bg-white border border-gray-100 text-gray-800 rounded-2xl rounded-bl-sm px-4 py-2.5 shadow-sm">
          <p className="text-sm leading-relaxed whitespace-pre-wrap">{message.text}</p>
        </div>
      </div>
    );
  }

  // Error message
  if (message.type === 'error') {
    return (
      <div className="flex justify-start px-4 py-1.5 animate-slide-in-left">
        <div className="max-w-[85%] sm:max-w-[75%] bg-red-50 border border-red-200 text-red-700 rounded-2xl rounded-bl-sm px-4 py-2.5 shadow-sm">
          <div className="flex items-start gap-2">
            <svg className="w-4 h-4 mt-0.5 shrink-0 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <p className="text-sm leading-relaxed">{message.text}</p>
          </div>
        </div>
      </div>
    );
  }

  // Flight results
  if (message.type === 'flight-results') {
    return (
      <div className="flex justify-start px-4 py-1.5 animate-slide-in-left">
        <div className="max-w-[90%] sm:max-w-[80%]">
          {message.text && (
            <div className="bg-white border border-gray-100 text-gray-800 rounded-2xl rounded-bl-sm px-4 py-2.5 shadow-sm mb-2">
              <p className="text-sm leading-relaxed">{message.text}</p>
            </div>
          )}
          <div className="space-y-2">
            {message.flights?.map((flight, idx) => (
              <FlightCardChat
                key={idx}
                flight={flight}
                onSelect={(f) => message.onSelectFlight?.(f)}
              />
            ))}
          </div>
          {(!message.flights || message.flights.length === 0) && (
            <div className="bg-white border border-gray-100 text-gray-500 rounded-2xl rounded-bl-sm px-4 py-3 shadow-sm text-center text-sm">
              Không tìm thấy chuyến bay phù hợp
            </div>
          )}
        </div>
      </div>
    );
  }

  // Booking confirmation
  if (message.type === 'booking-confirm') {
    return (
      <div className="flex justify-start px-4 py-1.5 animate-slide-in-left">
        <div className="max-w-[90%] sm:max-w-[80%]">
          {message.text && (
            <div className="bg-white border border-gray-100 text-gray-800 rounded-2xl rounded-bl-sm px-4 py-2.5 shadow-sm mb-2">
              <p className="text-sm leading-relaxed">{message.text}</p>
            </div>
          )}
          <BookingConfirmChat
            booking={message.booking || {}}
            onIssueTicket={(code) => message.onIssueTicket?.(code)}
            onCancel={(code) => message.onCancelBooking?.(code)}
          />
        </div>
      </div>
    );
  }

  return null;
}
