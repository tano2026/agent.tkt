'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import ChatMessage, { ChatMessageData } from '@/components/ChatMessage';
import { searchFlights, bookFlight, issueTicket } from '@/lib/api';

function generateId(): string {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
}

interface ExtendedFlight {
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
  StopQuantity?: number;
  SessionCode?: string;
  [key: string]: any;
}

export default function ChatBot() {
  const [messages, setMessages] = useState<ChatMessageData[]>([
    {
      id: generateId(),
      type: 'bot',
      text: 'Xin chào! Tôi là trợ lý đặt vé ABTrip. Bạn muốn đi đâu hôm nay?',
    },
  ]);
  const [inputValue, setInputValue] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [selectedFlight, setSelectedFlight] = useState<ExtendedFlight | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll to bottom
  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  // Auto-focus input
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // Add a message to the chat
  const addMessage = useCallback((msg: ChatMessageData) => {
    setMessages((prev) => [...prev, msg]);
  }, []);

  // Remove the last message (used for loading indicator)
  const removeLastMessage = useCallback(() => {
    setMessages((prev) => prev.slice(0, -1));
  }, []);

  // Show loading indicator
  const showLoading = useCallback(() => {
    addMessage({
      id: generateId(),
      type: 'loading',
    });
  }, [addMessage]);

  // Handle sending a message
  const handleSend = useCallback(async () => {
    const text = inputValue.trim();
    if (!text || isProcessing) return;

    setInputValue('');

    // Add user message
    addMessage({
      id: generateId(),
      type: 'user',
      text,
    });

    setIsProcessing(true);
    showLoading();

    try {
      const lower = text.toLowerCase();

      // Parse natural language for search intent
      const searchMatch = parseSearchIntent(text);

      if (searchMatch) {
        await handleFlightSearch(searchMatch);
      } else if (lower.includes('mã đặt') || lower.includes('book') || lower.includes('hủy') || lower.includes('huy')) {
        addMessage({
          id: generateId(),
          type: 'bot',
          text: 'Vui lòng nhập mã đặt chỗ của bạn để tôi tra cứu thông tin.',
        });
      } else if (lower.includes('cảm ơn') || lower.includes('thanks')) {
        addMessage({
          id: generateId(),
          type: 'bot',
          text: 'Cảm ơn bạn! Nếu cần hỗ trợ thêm, cứ nhắn cho tôi nhé. 🎉',
        });
      } else if (lower.includes('xin chào') || lower.includes('hello') || lower.includes('hi') || lower.includes('chào')) {
        addMessage({
          id: generateId(),
          type: 'bot',
          text: 'Xin chào! Bạn muốn tìm chuyến bay đi đâu hôm nay? Hãy thử nói: "Tìm chuyến bay từ Hà Nội vào Sài Gòn"',
        });
      } else if (lower.includes('giúp') || lower.includes('hỗ trợ') || lower.includes('help')) {
        addMessage({
          id: generateId(),
          type: 'bot',
          text: 'Tôi có thể giúp bạn:\n\n✈️ **Tìm chuyến bay**: Nói "Tìm chuyến bay từ [nơi đi] đến [nơi đến]" hoặc "Hà Nội vào Sài Gòn"\n💳 **Đặt vé**: Sau khi xem kết quả, chọn "Đặt ngay"\n🎫 **Xuất vé**: Dùng nút "Xuất vé" sau khi đặt\n📋 **Hủy đặt chỗ**: Dùng nút "Hủy"\n\nBạn muốn làm gì trước?',
        });
      } else {
        // Try to extract any route info from the text
        const routeInfo = extractRouteInfo(text);
        if (routeInfo) {
          await handleFlightSearch(routeInfo);
        } else {
          addMessage({
            id: generateId(),
            type: 'bot',
            text: 'Tôi chưa hiểu yêu cầu của bạn. Bạn có thể thử:\n\n• "Tìm chuyến bay từ Hà Nội vào Sài Gòn"\n• "Hà Nội đến Đà Nẵng"\n• "Chuyến bay từ Sài Gòn đi Nha Trang"\n\nHoặc gõ "giúp" để xem hướng dẫn chi tiết.',
          });
        }
      }
    } catch (err: any) {
      addMessage({
        id: generateId(),
        type: 'error',
        text: `Đã xảy ra lỗi: ${err.message || 'Vui lòng thử lại sau.'}`,
      });
    } finally {
      removeLastMessage();
      setIsProcessing(false);
      inputRef.current?.focus();
    }
  }, [inputValue, isProcessing, addMessage, showLoading, removeLastMessage]);

  // Handle flight search
  const handleFlightSearch = async (params: { origin: string; destination: string; date?: string }) => {
    try {
      const date = params.date || getDefaultDate();
      const result = await searchFlights({
        origin: params.origin,
        destination: params.destination,
        departDate: date,
        adults: 1,
      });

      // Check if we got real results or mock
      let flights: ExtendedFlight[] = [];
      let foundFromMock = false;

      if (result.Success && result.Result?.Flights) {
        flights = result.Result.Flights;
      } else if (result.Success && Array.isArray(result.Result)) {
        flights = result.Result;
      } else if (result.mock) {
        flights = result.data || [];
        foundFromMock = true;
      }

      const airportNames: Record<string, string> = {
        HAN: 'Hà Nội', SGN: 'Hồ Chí Minh', DAD: 'Đà Nẵng',
        CXR: 'Nha Trang', VII: 'Vinh', HUI: 'Huế', PQC: 'Phú Quốc',
      };

      const fromName = airportNames[params.origin] || params.origin;
      const toName = airportNames[params.destination] || params.destination;

      if (flights.length > 0) {
        addMessage({
          id: generateId(),
          type: 'flight-results',
          text: foundFromMock
            ? `Đã tìm thấy ${flights.length} chuyến bay từ ${fromName} đến ${toName}:`
            : `Có ${flights.length} chuyến bay từ ${fromName} đến ${toName}:`,
          flights,
          onSelectFlight: (flight) => handleSelectFlight(flight),
        });
      } else {
        addMessage({
          id: generateId(),
          type: 'bot',
          text: `Rất tiếc, không tìm thấy chuyến bay nào từ ${fromName} đến ${toName}. Vui lòng thử tuyến đường khác hoặc ngày khác.`,
        });
      }
    } catch (err: any) {
      addMessage({
        id: generateId(),
        type: 'error',
        text: `Không thể tìm kiếm chuyến bay: ${err.message || 'Vui lòng thử lại sau.'}`,
      });
    }
  };

  // Handle flight selection -> simulate booking
  const handleSelectFlight = async (flight: ExtendedFlight) => {
    setSelectedFlight(flight);
    setIsProcessing(true);
    showLoading();

    try {
      // Simulate booking with mock data
      const mockPassenger = {
        title: 'Mr',
        lastName: 'Nguyen',
        firstName: 'Van A',
        gender: 'M',
        birthDate: '01011990',
        type: 'adult' as const,
      };

      let bookingResult: any;

      try {
        bookingResult = await bookFlight({
          sessionCode: flight.SessionCode || 'MOCK_SESSION',
          passengers: [mockPassenger],
        });
      } catch {
        // If API fails, create mock booking
        bookingResult = {
          Success: true,
          BookingCode: 'AB' + Math.random().toString(36).slice(2, 8).toUpperCase(),
          BookingStatus: 'CONFIRMED',
        };
      }

      const bookingCode = bookingResult.BookingCode || 'AB' + Math.random().toString(36).slice(2, 8).toUpperCase();

      addMessage({
        id: generateId(),
        type: 'booking-confirm',
        text: `Bạn đã chọn chuyến bay ${flight.AirlineCode} ${flight.FlightNumber} từ ${flight.DepartAirport} đến ${flight.ArrivalAirport}. Đang tiến hành đặt vé...`,
        booking: {
          BookingCode: bookingCode,
          BookingStatus: 'CONFIRMED',
          AirlineCode: flight.AirlineCode,
          FlightNumber: flight.FlightNumber,
          DepartAirport: flight.DepartAirport,
          ArrivalAirport: flight.ArrivalAirport,
          DepartDate: flight.DepartDate,
          DepartTime: flight.DepartTime,
          ArrivalDate: flight.ArrivalDate,
          ArrivalTime: flight.ArrivalTime,
          AdultFare: flight.AdultFare,
          TotalFare: flight.AdultFare,
          Currency: flight.Currency || 'VND',
          Passengers: [{
            Title: 'Mr',
            FirstName: 'Van A',
            LastName: 'Nguyen',
            Type: 'adult',
          }],
        },
        onIssueTicket: (code) => handleIssueTicket(code),
        onCancelBooking: (code) => handleCancelBooking(code),
      });
    } catch (err: any) {
      addMessage({
        id: generateId(),
        type: 'error',
        text: `Đặt vé thất bại: ${err.message || 'Vui lòng thử lại.'}`,
      });
    } finally {
      removeLastMessage();
      setIsProcessing(false);
    }
  };

  // Handle issue ticket
  const handleIssueTicket = async (code: string) => {
    setIsProcessing(true);
    showLoading();

    try {
      await issueTicket(code);
      addMessage({
        id: generateId(),
        type: 'bot',
        text: `✅ Vé cho mã đặt chỗ **${code}** đã được xuất thành công! Vui lòng kiểm tra email để nhận vé điện tử.`,
      });
    } catch (err: any) {
      addMessage({
        id: generateId(),
        type: 'error',
        text: `Xuất vé thất bại: ${err.message || 'Vui lòng thử lại.'}`,
      });
    } finally {
      removeLastMessage();
      setIsProcessing(false);
    }
  };

  // Handle cancel booking
  const handleCancelBooking = async (code: string) => {
    addMessage({
      id: generateId(),
      type: 'bot',
      text: `Đã nhận yêu cầu hủy đặt chỗ **${code}**. Vui lòng liên hệ hotline 1900 XXX XXX để được hỗ trợ hủy vé.`,
    });
  };

  // Parse natural language for search intent
  const parseSearchIntent = (text: string): { origin: string; destination: string; date?: string } | null => {
    const lower = text.toLowerCase();

    // Airport code mapping
    const cityToCode: Record<string, string> = {
      'hà nội': 'HAN', 'ha noi': 'HAN', 'hanoi': 'HAN',
      'sài gòn': 'SGN', 'saigon': 'SGN', 'sai gon': 'SGN', 'hồ chí minh': 'SGN', 'ho chi minh': 'SGN', 'hcm': 'SGN',
      'đà nẵng': 'DAD', 'da nang': 'DAD', 'danang': 'DAD',
      'nha trang': 'CXR', 'nhatrang': 'CXR', 'nha trang': 'CXR',
      'vinh': 'VII',
      'huế': 'HUI', 'hue': 'HUI',
      'phú quốc': 'PQC', 'phu quoc': 'PQC',
    };

    // Try to find pattern: "từ X đến Y" or "X đến Y" or "X - Y"
    let origin: string | null = null;
    let destination: string | null = null;
    let date: string | undefined;

    // Pattern: "từ [origin] [đến|vào|ra] [destination]"
    const patterns = [
      /từ\s+(.+?)\s+(?:đến|vào|ra|qua|sang)\s+(.+?)(?:$|\s+ngày\s+|\s+\d+)/i,
      /(.+?)\s+(?:đến|vào|ra|qua|sang)\s+(.+?)(?:$|\s+ngày\s+|\s+\d+)/i,
      /(.+?)\s*[-–—]\s*(.+?)(?:$|\s)/i,
    ];

    for (const pattern of patterns) {
      const match = lower.match(pattern);
      if (match) {
        origin = match[1].trim();
        destination = match[2].trim();

        // Clean up common words
        origin = origin.replace(/\b(chuyến bay|tìm|cho|mình|giúp)\b/gi, '').trim();
        destination = destination.replace(/\b(chuyến bay|cho|mình)\b/gi, '').trim();

        // Map to airport codes
        const originCode = cityToCode[origin];
        const destCode = cityToCode[destination];

        if (originCode && destCode) {
          // Check for date
          const dateMatch = lower.match(/ngày\s+(\d{1,2})[\/\-](\d{1,2})(?:[\/\-](\d{2,4}))?/);
          if (dateMatch) {
            const day = dateMatch[1].padStart(2, '0');
            const month = dateMatch[2].padStart(2, '0');
            const year = dateMatch[3] ? (dateMatch[3].length === 2 ? '20' + dateMatch[3] : dateMatch[3]) : '2026';
            date = `${day}${month}${year}`;
          }
          return { origin: originCode, destination: destCode, date };
        }
        break;
      }
    }

    return null;
  };

  // Extract route info from general text
  const extractRouteInfo = (text: string): { origin: string; destination: string; date?: string } | null => {
    return parseSearchIntent(text); // Same logic
  };

  // Get default date (today + 7 days)
  const getDefaultDate = (): string => {
    const d = new Date();
    d.setDate(d.getDate() + 7);
    const day = String(d.getDate()).padStart(2, '0');
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const year = d.getFullYear();
    return `${day}${month}${year}`;
  };

  // Handle Enter key (Shift+Enter for new line)
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // Auto-resize textarea
  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInputValue(e.target.value);
    if (e.target) {
      e.target.style.height = 'auto';
      e.target.style.height = Math.min(e.target.scrollHeight, 150) + 'px';
    }
  };

  return (
    <div className="flex flex-col h-screen bg-blue-50">
      {/* Messages area */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto py-4">
          {messages.map((msg) => (
            <ChatMessage key={msg.id} message={msg} />
          ))}
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input area */}
      <div className="border-t border-gray-200 bg-white px-4 py-3 shadow-lg">
        <div className="max-w-3xl mx-auto">
          <div className="flex items-end gap-2 bg-gray-50 rounded-2xl border border-gray-200 focus-within:border-blue-400 focus-within:ring-2 focus-within:ring-blue-100 transition-all px-4 py-2">
            <textarea
              ref={inputRef}
              value={inputValue}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
              placeholder="Nhập tin nhắn..."
              rows={1}
              disabled={isProcessing}
              className="flex-1 bg-transparent text-sm text-gray-800 placeholder-gray-400 outline-none resize-none max-h-[150px] py-1.5"
              style={{ scrollbarWidth: 'thin' }}
            />
            <button
              onClick={handleSend}
              disabled={!inputValue.trim() || isProcessing}
              className={`shrink-0 w-9 h-9 rounded-xl flex items-center justify-center transition-all ${
                inputValue.trim() && !isProcessing
                  ? 'bg-blue-500 text-white hover:bg-blue-600 active:bg-blue-700 shadow-sm'
                  : 'bg-gray-200 text-gray-400 cursor-not-allowed'
              }`}
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 12h14M12 5l7 7-7 7" />
              </svg>
            </button>
          </div>
          <p className="text-[10px] text-gray-400 text-center mt-1.5">
            ABTrip hỗ trợ tìm kiếm và đặt vé máy bay
          </p>
        </div>
      </div>
    </div>
  );
}
