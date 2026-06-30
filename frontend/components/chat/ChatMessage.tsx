'use client';

interface ChatMessageProps {
  role: 'user' | 'assistant' | 'system';
  content: string;
  isLatest?: boolean;
}

export default function ChatMessage({ role, content, isLatest }: ChatMessageProps) {
  if (role === 'system') return null;

  const isUser = role === 'user';

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} px-3 sm:px-4`}>
      <div
        className={`max-w-[85%] sm:max-w-[75%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap ${
          isUser
            ? 'bg-blue-600 text-white rounded-br-md'
            : 'bg-white text-gray-800 border border-gray-100 shadow-sm rounded-bl-md'
        } ${isLatest ? 'animate-fade-in' : ''}`}
      >
        <div className={isUser ? 'text-white' : 'text-gray-800'}>
          {content.split('\n').map((line, i) => (
            <span key={i}>
              {line}
              {i < content.split('\n').length - 1 && <br />}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
