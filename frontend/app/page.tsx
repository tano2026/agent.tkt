"use client";

import { useState } from "react";
import ChatPanel from "../components/ChatPanel";

type Agent = "ticketing" | "sim" | "visa";

const TAB_CONFIG: Record<Agent, { label: string; icon: string; color: string }> = {
  ticketing: { label: "Vé máy bay", icon: "✈️", color: "from-blue-500 to-cyan-500" },
  sim: { label: "SIM du lịch", icon: "📱", color: "from-emerald-500 to-teal-500" },
  visa: { label: "Visa & Hộ chiếu", icon: "🛂", color: "from-violet-500 to-purple-500" },
};

export default function Home() {
  const [activeTab, setActiveTab] = useState<Agent>("ticketing");
  const active = TAB_CONFIG[activeTab];

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-4 py-3">
        <div className="max-w-2xl mx-auto flex items-center gap-3">
          <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-cyan-500 rounded-xl flex items-center justify-center text-white text-sm font-bold">
            A
          </div>
          <div>
            <h1 className="text-sm font-semibold text-gray-900 leading-tight">ABTrip AI Agent</h1>
            <p className="text-[10px] text-gray-500">Đặt vé, eSIM & Visa thông minh</p>
          </div>
        </div>
      </header>

      {/* Tab bar */}
      <div className="bg-white border-b border-gray-100 px-4 py-2">
        <div className="max-w-2xl mx-auto flex gap-2">
          {(["ticketing", "sim", "visa"] as Agent[]).map((tab) => {
            const cfg = TAB_CONFIG[tab];
            const isActive = tab === activeTab;
            return (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-xl text-xs font-medium transition-all ${
                  isActive
                    ? `bg-gradient-to-r ${cfg.color} text-white shadow-md`
                    : "bg-gray-50 text-gray-500 hover:bg-gray-100"
                }`}
              >
                <span>{cfg.icon}</span>
                <span className="hidden sm:inline">{cfg.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Chat area */}
      <div className="flex-1 overflow-hidden">
        <div className="h-full max-w-2xl mx-auto">
          {activeTab === "ticketing" && <ChatPanel agent="ticketing" />}
          {activeTab === "sim" && <ChatPanel agent="sim" />}
          {activeTab === "visa" && <ChatPanel agent="visa" />}
        </div>
      </div>
    </div>
  );
}
