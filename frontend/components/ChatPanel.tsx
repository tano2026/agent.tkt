"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";

// -----------------------------------------------------------------------
// Types
// -----------------------------------------------------------------------

type Agent = "ticketing" | "sim" | "visa";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  type?: "text" | "flight_results" | "sim_results" | "visa_info" | "booking_confirm";
  timestamp: number;
  suggestions?: string[];
}

// -----------------------------------------------------------------------
// Chat API
// -----------------------------------------------------------------------

const API_BASE = process.env.NEXT_PUBLIC_API_URL || process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8137";

async function sendChat(message: string, agent: Agent, sessionId: string): Promise<{
  reply: string;
  type: string;
  suggestions?: string[];
  session_id?: string;
}> {
  const res = await fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, agent, session_id: sessionId }),
  });
  if (!res.ok) {
    throw new Error(`Lỗi ${res.status}: ${res.statusText}`);
  }
  const data = await res.json();
  // Backend may return "content" or "reply"
  return {
    reply: data.reply || data.content || "Không có phản hồi",
    type: data.type || "text",
    suggestions: data.suggestions,
    session_id: data.session_id,
  };
}

// -----------------------------------------------------------------------
// Icon components
// -----------------------------------------------------------------------

const Icons = {
  user: () => (
    <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" />
    </svg>
  ),
  bot: (agent: Agent) => {
    const icons: Record<Agent, JSX.Element> = {
      ticketing: <><text x="12" y="16" textAnchor="middle" fontSize="14">✈️</text></>,
      sim: <><text x="12" y="16" textAnchor="middle" fontSize="14">📱</text></>,
      visa: <><text x="12" y="16" textAnchor="middle" fontSize="14">🛂</text></>,
    };
    return (
      <svg className="w-7 h-7" viewBox="0 0 24 24">
        {icons[agent]}
      </svg>
    );
  },
  send: () => (
    <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" />
    </svg>
  ),
  spinner: () => (
    <svg className="w-5 h-5 animate-spin" viewBox="0 0 24 24" fill="none">
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" opacity="0.25" />
      <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" strokeWidth="4" strokeLinecap="round" />
    </svg>
  ),
};

// -----------------------------------------------------------------------
// Agent config
// -----------------------------------------------------------------------

const AGENT_CONFIG: Record<Agent, {
  label: string;
  icon: string;
  color: string;
  gradient: string;
  placeholder: string;
  welcome: string;
}> = {
  ticketing: {
    label: "Vé máy bay",
    icon: "✈️",
    color: "from-blue-500 to-cyan-500",
    gradient: "from-blue-50 to-cyan-50",
    placeholder: "Tìm chuyến bay... VD: SG HN ngày mai 2 người",
    welcome: "✈️ Chào bạn! Tôi là trợ lý đặt vé. Bạn cần tìm chuyến bay, tra cứu thủ tục hay chính sách hãng? Cứ nói tự nhiên nhé!",
  },
  sim: {
    label: "SIM du lịch",
    icon: "📱",
    color: "from-emerald-500 to-teal-500",
    gradient: "from-emerald-50 to-teal-50",
    placeholder: "VD: eSIM Thái Lan 7 ngày",
    welcome: "📱 Chào bạn! Bạn cần mua eSIM du lịch cho nước nào? Tôi sẽ tư vấn gói phù hợp nhất!",
  },
  visa: {
    label: "Visa & Hộ chiếu",
    icon: "🛂",
    color: "from-violet-500 to-purple-500",
    gradient: "from-violet-50 to-purple-50",
    placeholder: "VD: visa du lịch Nhật Bản",
    welcome: "🛂 Chào bạn! Tôi chuyên tư vấn visa & hộ chiếu. Bạn định đi nước nào? Mình cùng tìm hiểu thủ tục nhé!",
  },
};

// -----------------------------------------------------------------------
// ChatBubble component
// -----------------------------------------------------------------------

function ChatBubble({ msg, agent }: { msg: Message; agent: Agent }) {
  const isUser = msg.role === "user";

  // Parse markdown-like formatting
  const renderContent = (text: string) => {
    // Bold **text**
    let html = text
      .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
      .replace(/\*(.*?)\*/g, "<em>$1</em>")
      .replace(/\n/g, "<br/>");
    return html;
  };

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-3 animate-fadeIn`}>
      <div className={`flex gap-2 max-w-[85%] md:max-w-[75%] ${isUser ? "flex-row-reverse" : ""}`}>
        {/* Avatar */}
        <div className={`flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center text-sm ${
          isUser
            ? "bg-blue-500 text-white"
            : `bg-gradient-to-br ${AGENT_CONFIG[agent].color} text-white`
        }`}>
          {isUser ? (
            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" />
            </svg>
          ) : (
            <span className="text-xs">{AGENT_CONFIG[agent].icon}</span>
          )}
        </div>

        {/* Content */}
        <div>
          <div
            className={`rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
              isUser
                ? "bg-blue-500 text-white rounded-tr-md"
                : "bg-white border border-gray-200 shadow-sm rounded-tl-md"
            }`}
            dangerouslySetInnerHTML={{ __html: renderContent(msg.content) }}
          />

          {/* Suggestions */}
          {msg.suggestions && msg.suggestions.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {msg.suggestions.map((s, i) => (
                <span
                  key={i}
                  className="px-3 py-1 text-xs bg-gray-100 text-gray-600 rounded-full border border-gray-200 cursor-pointer hover:bg-gray-200 transition-colors"
                >
                  {s}
                </span>
              ))}
            </div>
          )}

          {/* Timestamp */}
          <p className={`text-[10px] mt-1 text-gray-400 ${isUser ? "text-right" : ""}`}>
            {new Date(msg.timestamp).toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" })}
          </p>
        </div>
      </div>
    </div>
  );
}

// -----------------------------------------------------------------------
// Main Chat component
// -----------------------------------------------------------------------

interface ChatPanelProps {
  agent: Agent;
}

export default function ChatPanel({ agent }: ChatPanelProps) {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      role: "assistant",
      content: AGENT_CONFIG[agent].welcome,
      type: "text",
      timestamp: Date.now(),
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sessionId] = useState(() => `session_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const config = AGENT_CONFIG[agent];

  // Auto scroll to bottom
  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  // Focus input on mount & agent change
  useEffect(() => {
    inputRef.current?.focus();
  }, [agent]);

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || loading) return;
    setInput("");

    const userMsg: Message = {
      id: `user_${Date.now()}`,
      role: "user",
      content: text,
      timestamp: Date.now(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    try {
      const data = await sendChat(text, agent, sessionId);
      const botMsg: Message = {
        id: `bot_${Date.now()}`,
        role: "assistant",
        content: data.reply,
        type: (data.type as Message["type"]) || "text",
        timestamp: Date.now(),
        suggestions: data.suggestions,
      };
      setMessages((prev) => [...prev, botMsg]);
    } catch (err: unknown) {
      const errorMsg: Message = {
        id: `err_${Date.now()}`,
        role: "assistant",
        content: `❌ Lỗi kết nối: ${err instanceof Error ? err.message : "Không thể kết nối đến server"}. Vui lòng thử lại.`,
        type: "text",
        timestamp: Date.now(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    }
    setLoading(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const handleSuggestionClick = (suggestion: string) => {
    setInput(suggestion);
    // Auto send after short delay
    setTimeout(() => {
      const fakeEvent = { target: { value: suggestion } } as React.ChangeEvent<HTMLInputElement>;
      setInput(suggestion);
    }, 0);
  };

  return (
    <div className="flex flex-col h-full">
      {/* Messages area */}
      <div className={`flex-1 overflow-y-auto px-4 py-4 bg-gradient-to-b ${config.gradient}`}>
        {messages.map((msg) => (
          <ChatBubble key={msg.id} msg={msg} agent={agent} />
        ))}

        {/* Typing indicator */}
        {loading && (
          <div className="flex justify-start mb-3 animate-fadeIn">
            <div className="flex gap-2">
              <div className={`w-7 h-7 rounded-full flex items-center justify-center bg-gradient-to-br ${config.color} text-white text-xs`}>
                {config.icon}
              </div>
              <div className="bg-white border border-gray-200 shadow-sm rounded-2xl rounded-tl-md px-4 py-3">
                <div className="flex gap-1.5">
                  <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                  <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                  <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                </div>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <div className="border-t border-gray-200 bg-white px-4 py-3">
        <div className="flex gap-2 items-center">
          <div className="flex-1 relative">
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={config.placeholder}
              disabled={loading}
              className="w-full px-4 py-3 pr-10 bg-gray-50 border border-gray-200 rounded-2xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent disabled:opacity-50 transition-all"
            />
          </div>
          <button
            onClick={sendMessage}
            disabled={loading || !input.trim()}
            className={`w-11 h-11 rounded-2xl flex items-center justify-center text-white transition-all ${
              loading
                ? "bg-gray-300"
                : input.trim()
                ? `bg-gradient-to-r ${config.color} shadow-md hover:shadow-lg active:scale-95`
                : "bg-gray-200"
            }`}
          >
            {loading ? <Icons.spinner /> : <Icons.send />}
          </button>
        </div>

        {/* Quick actions */}
        <div className="flex gap-2 mt-2 overflow-x-auto pb-1 scrollbar-hide">
          {agent === "ticketing" && (
            <>
              <button
                onClick={() => setInput("Hành lý Vietnam Airlines được bao nhiêu kg?")}
                className="px-3 py-1.5 text-xs bg-gray-50 border border-gray-200 rounded-full whitespace-nowrap hover:bg-gray-100 transition-colors shrink-0"
              >
                🧳 Hành lý VNA
              </button>
              <button
                onClick={() => setInput("Tìm vé SG HN ngày mai 1 người")}
                className="px-3 py-1.5 text-xs bg-gray-50 border border-gray-200 rounded-full whitespace-nowrap hover:bg-gray-100 transition-colors shrink-0"
              >
                ✈️ SG→HN mai
              </button>
              <button
                onClick={() => setInput("Chính sách đổi vé VietJet")}
                className="px-3 py-1.5 text-xs bg-gray-50 border border-gray-200 rounded-full whitespace-nowrap hover:bg-gray-100 transition-colors shrink-0"
              >
                🔄 Đổi vé VJ
              </button>
            </>
          )}
          {agent === "sim" && (
            <>
              <button
                onClick={() => setInput("eSIM Thái Lan 7 ngày giá bao nhiêu?")}
                className="px-3 py-1.5 text-xs bg-gray-50 border border-gray-200 rounded-full whitespace-nowrap hover:bg-gray-100 transition-colors shrink-0"
              >
                🇹🇭 eSIM Thái
              </button>
              <button
                onClick={() => setInput("Gói eSIM nào dùng nhiều data nhất?")}
                className="px-3 py-1.5 text-xs bg-gray-50 border border-gray-200 rounded-full whitespace-nowrap hover:bg-gray-100 transition-colors shrink-0"
              >
                📶 Data nhiều
              </button>
            </>
          )}
          {agent === "visa" && (
            <>
              <button
                onClick={() => setInput("Visa du lịch Nhật Bản cần giấy tờ gì?")}
                className="px-3 py-1.5 text-xs bg-gray-50 border border-gray-200 rounded-full whitespace-nowrap hover:bg-gray-100 transition-colors shrink-0"
              >
                🇯🇵 Visa Nhật
              </button>
              <button
                onClick={() => setInput("Visa Hàn Quốc bao lâu có?")}
                className="px-3 py-1.5 text-xs bg-gray-50 border border-gray-200 rounded-full whitespace-nowrap hover:bg-gray-100 transition-colors shrink-0"
              >
                🇰🇷 Visa Hàn
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
