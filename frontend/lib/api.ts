const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8765';

// ─── Chat API (new) ──────────────────────────────────────────────────────────

export interface Message {
  role: 'user' | 'assistant' | 'system';
  content: string;
  type?: 'text';
  data?: any;
}

export interface ChatResponse {
  type: 'text' | 'tool_call' | 'error' | 'booking_result';
  content: string | Record<string, any>;
  session_id: string;
  suggestions: string[];
}

export interface AgentInfo {
  id: string;
  name: string;
  icon: string;
  description: string;
  gradient: string;
}

export async function sendChatMessage(
  agent: string,
  message: string,
  sessionId?: string
): Promise<ChatResponse> {
  const res = await fetch(`${BACKEND_URL}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ agent, message, session_id: sessionId }),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function getAgents(): Promise<AgentInfo[]> {
  const res = await fetch(`${BACKEND_URL}/api/agents`);
  if (!res.ok) return [];
  const data = await res.json();
  return data.agents || [];
}

// ─── Search/Book API (old, used by search/ and book/ pages) ──────────────────

export interface SearchParams {
  startPoint?: string;
  endPoint?: string;
  origin?: string;
  destination?: string;
  departDate: string;
  returnDate?: string;
  adt?: number;
  chd?: number;
  inf?: number;
  directFlight?: boolean;
  [key: string]: any;
}

export async function searchFlights(params: SearchParams): Promise<any> {
  const res = await fetch(`${BACKEND_URL}/api/flights/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  if (!res.ok) throw new Error(`Search failed: ${res.status}`);
  return res.json();
}

export interface BookParams {
  bookingCode?: string;
  session?: string;
  sessionCode?: string;
  passengers?: any[];
  contactInfo?: any;
  flightInfo?: any;
  [key: string]: any;
}

export async function bookFlight(params: BookParams): Promise<any> {
  const res = await fetch(`${BACKEND_URL}/api/flights/book`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  if (!res.ok) throw new Error(`Booking failed: ${res.status}`);
  return res.json();
}

export async function getChatHistory(sessionId: string): Promise<Message[]> {
  const res = await fetch(`${BACKEND_URL}/api/chat/history/${sessionId}`);
  if (!res.ok) return [];
  const data = await res.json();
  return data.messages || [];
}

export async function getAirports(): Promise<any> {
  try {
    const res = await fetch(`${BACKEND_URL}/api/reference/airports`);
    if (!res.ok) return { StatusCode: '500', Result: [] };
    return await res.json();
  } catch {
    return { StatusCode: '500', Result: [] };
  }
}
