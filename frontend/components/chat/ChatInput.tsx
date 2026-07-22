'use client';

import { useState, useRef, useEffect, KeyboardEvent } from 'react';

interface ChatInputProps {
  onSend: (message: string) => void;
  disabled?: boolean;
  placeholder?: string;
}

export default function ChatInput({ onSend, disabled, placeholder }: ChatInputProps) {
  const [text, setText] = useState('');
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (!disabled && inputRef.current) {
      inputRef.current.focus();
    }
  }, [disabled]);

  const handleSend = () => {
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setText('');
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // Auto-resize textarea
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = 'auto';
      inputRef.current.style.height = Math.min(inputRef.current.scrollHeight, 120) + 'px';
    }
  }, [text]);

  return (
    <div className="border-t border-gray-100 bg-white px-4 py-3">
      <div className="flex items-end gap-2 max-w-2xl mx-auto">
        <div className="flex-1 flex items-end gap-1.5 bg-gray-100 rounded-2xl px-4 py-2.5 focus-within:bg-gray-50 focus-within:ring-2 focus-within:ring-gray-200 transition-all">
          <textarea
            ref={inputRef}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder || 'Nhắn tin tự nhiên...'}
            disabled={disabled}
            rows={1}
            className="flex-1 resize-none bg-transparent text-sm outline-none placeholder:text-gray-400 disabled:opacity-50 leading-relaxed"
          />
          <button
            onClick={handleSend}
            disabled={disabled || !text.trim()}
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gray-900 text-white transition-all hover:bg-gray-800 active:scale-95 disabled:opacity-30 disabled:active:scale-100"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="22" y1="2" x2="11" y2="13" />
              <polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}
