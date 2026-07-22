'use client';

import { useState, useRef, useEffect } from 'react';
import ChatMessage from './ChatMessage';
import ChatInput from './ChatInput';
import { sendChatMessage, Message } from '@/lib/api';

interface ChatInterfaceProps {
  agent: 'ticketing' | 'sim' | 'visa';
}

const WELCOME_MESSAGES: Record<string, string> = {
  ticketing: 'Xin chào! Tôi là trợ lý đặt vé máy bay. Bạn muốn tìm chuyến bay đi đâu? Cứ nói tự nhiên nhé!\n\n💡 Ví dụ: "tìm HN SG ngày mai 2 người" hoặc "vé rẻ nhất Đà Nẵng cuối tuần"',
  sim: 'Xin chào! Tôi là trợ lý SIM du lịch. Bạn muốn tìm eSIM/SIM cho nước nào?\n\n💡 Ví dụ: "eSIM Thái Lan" hoặc "SIM du lịch Nhật Bản 7 ngày"',
  visa: 'Xin chào! Tôi là chuyên gia tư vấn Visa & Hộ chiếu. Bạn muốn tìm hiểu thủ tục đi nước nào?\n\n💡 Ví dụ: "visa Nhật cần gì?" hoặc "thủ tục xin visa Hàn Quốc"',
};

const LOADING_DOTS = [
  { delay: '0ms' },
  { delay: '200ms' },
  { delay: '400ms' },
];

export default function ChatInterface({ agent }: ChatInterfaceProps) {
  const [messages, setMessages] = useState<Message[]>([
    { role: 'assistant', content: WELCOME_MESSAGES[agent] || WELCOME_MESSAGES.ticketing },
  ]);
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | undefined>();
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Scroll to bottom on new messages
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages]);

  // Reset when agent changes
  useEffect(() => {
    setMessages([{ role: 'assistant', content: WELCOME_MESSAGES[agent] || WELCOME_MESSAGES.ticketing }]);
    setSessionId(undefined);
    setSuggestions([]);
    setIsLoading(false);
  }, [agent]);

  const handleSend = async (text: string) => {
    const userMessage: Message = { role: 'user', content: text };
    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);
    setSuggestions([]);

    try {
      const res = await sendChatMessage(agent, text, sessionId);

      if (res.session_id && !sessionId) {
        setSessionId(res.session_id);
      }

      // Add assistant response
      const content = typeof res.content === 'string' ? res.content : JSON.stringify(res.content, null, 2);
      const assistantMessage: Message = { role: 'assistant', content };
      setMessages((prev) => [...prev, assistantMessage]);

      if (res.suggestions?.length) {
        setSuggestions(res.suggestions);
      }
    } catch (err: any) {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: `❌ Lỗi kết nối: ${err.message}. Vui lòng thử lại.` },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSuggestionClick = (suggestion: string) => {
    handleSend(suggestion);
  };

  return (
    <div className="flex flex-col h-full" style={{ height: 'calc(100vh - 130px)' }}>
      {/* Messages area */}
      <div
        ref={containerRef}
        className="flex-1 overflow-y-auto py-6 space-y-4 scroll-smooth"
        style={{ scrollBehavior: 'smooth' }}
      >
        {messages.map((msg, i) => (
          <ChatMessage
            key={i}
            role={msg.role}
            content={msg.content}
            isLatest={i === messages.length - 1}
          />
        ))}

        {/* Loading indicator — ChatGPT-style dots */}
        {isLoading && (
          <div className="flex justify-start px-4 sm:px-6">
            <div className="flex items-center gap-1.5 px-1 py-1">
              {LOADING_DOTS.map((dot, i) => (
                <span
                  key={i}
                  className="w-2 h-2 bg-gray-400 rounded-full animate-pulse-dot"
                  style={{ animationDelay: dot.delay }}
                />
              ))}
            </div>
          </div>
        )}

        {/* Suggestions */}
        {suggestions.length > 0 && !isLoading && (
          <div className="flex flex-wrap gap-2 px-4 sm:px-6 pt-1">
            {suggestions.map((s, i) => (
              <button
                key={i}
                onClick={() => handleSuggestionClick(s)}
                className="px-3.5 py-1.5 text-sm text-gray-600 bg-gray-100 rounded-full hover:bg-gray-200 transition-colors active:scale-95"
              >
                {s}
              </button>
            ))}
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <ChatInput
        onSend={handleSend}
        disabled={isLoading}
      />
    </div>
  );
}
