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
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} px-4 sm:px-6`}>
      <div
        className={`max-w-[85%] sm:max-w-[75%] text-sm leading-relaxed whitespace-pre-wrap ${
          isUser
            ? 'bg-gray-900 text-white rounded-2xl rounded-br-sm px-4 py-2.5'
            : 'text-gray-800 px-1 py-0.5'
        } ${isLatest ? 'animate-fade-in' : ''}`}
      >
        {isUser ? (
          <div>{content}</div>
        ) : (
          <div className="text-gray-800 leading-relaxed">
            {content.split('\n').map((line, i) => (
              <span key={i}>
                {line}
                {i < content.split('\n').length - 1 && <br />}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
