'use client';

import { useState } from 'react';
import ChatInterface from '@/components/chat/ChatInterface';

type Agent = 'ticketing' | 'sim' | 'visa';

interface TabConfig {
  id: Agent;
  label: string;
  icon: string;
  gradient: string;
  activeGradient: string;
}

const TABS: TabConfig[] = [
  {
    id: 'ticketing',
    label: 'Vé máy bay',
    icon: '✈️',
    gradient: 'from-blue-600 to-blue-800',
    activeGradient: 'bg-gradient-to-r from-blue-600 to-blue-700',
  },
  {
    id: 'sim',
    label: 'SIM du lịch',
    icon: '📱',
    gradient: 'from-emerald-600 to-emerald-800',
    activeGradient: 'bg-gradient-to-r from-emerald-600 to-emerald-700',
  },
  {
    id: 'visa',
    label: 'Visa & Hộ chiếu',
    icon: '🛂',
    gradient: 'from-violet-600 to-violet-800',
    activeGradient: 'bg-gradient-to-r from-violet-600 to-violet-700',
  },
];

export default function Home() {
  const [activeTab, setActiveTab] = useState<Agent>('ticketing');

  const activeTabConfig = TABS.find((t) => t.id === activeTab)!;

  return (
    <div className="flex flex-col min-h-screen bg-gray-50">
      {/* Sticky header with tab bar */}
      <div className="sticky top-0 z-50">
        {/* Header */}
        <div className={`bg-gradient-to-r ${activeTabConfig.gradient} text-white`}>
          <div className="px-4 py-3 max-w-2xl mx-auto">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-lg font-bold tracking-tight">ABTrip</span>
                <span className="text-xs opacity-70">AI Agent</span>
              </div>
              <div className="flex items-center gap-1 text-xs opacity-70">
                <span>🔒 Bảo mật</span>
              </div>
            </div>
          </div>
        </div>

        {/* Tab bar */}
        <div className="bg-white border-b border-gray-100 shadow-sm">
          <div className="max-w-2xl mx-auto px-2">
            <div className="flex">
              {TABS.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex-1 flex items-center justify-center gap-1.5 py-3 text-sm font-medium transition-all relative ${
                    activeTab === tab.id
                      ? 'text-gray-900'
                      : 'text-gray-400 hover:text-gray-600'
                  }`}
                >
                  <span className="text-base">{tab.icon}</span>
                  <span className="hidden sm:inline">{tab.label}</span>
                  <span className="sm:hidden text-xs">{tab.label.split(' ')[0]}</span>
                  {activeTab === tab.id && (
                    <span
                      className={`absolute bottom-0 left-2 right-2 h-0.5 rounded-full ${
                        tab.id === 'ticketing'
                          ? 'bg-blue-500'
                          : tab.id === 'sim'
                          ? 'bg-emerald-500'
                          : 'bg-violet-500'
                      }`}
                    />
                  )}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Main content — chat area */}
      <div className="flex-1 flex flex-col">
        <div className="flex-1 max-w-2xl mx-auto w-full">
          {/* Agent welcome banner */}
          <div className="px-4 py-3">
            <div className="flex items-center gap-3">
              <span className="text-2xl">{activeTabConfig.icon}</span>
              <div>
                <h2 className="font-semibold text-gray-900 text-sm">
                  {activeTabConfig.label}
                </h2>
                <p className="text-xs text-gray-500">
                  {activeTab === 'ticketing'
                    ? 'Tìm & đặt vé máy bay bằng chat tự nhiên'
                    : activeTab === 'sim'
                    ? 'Tìm gói SIM/eSIM du lịch'
                    : 'Tư vấn thủ tục visa & hộ chiếu'}
                </p>
              </div>
            </div>
          </div>

          {/* Chat interface */}
          <ChatInterface key={activeTab} agent={activeTab} />
        </div>
      </div>

      {/* Mobile bottom padding for input */}
      <div className="h-2" />
    </div>
  );
}
