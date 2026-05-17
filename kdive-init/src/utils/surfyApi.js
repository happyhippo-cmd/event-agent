'use client';

const DEFAULT_CHAT_API_URL = 'http://localhost:8000/api/chat/';

export function getSurfyApiUrl(path) {
  const chatUrl = (
    typeof window !== 'undefined' && window.KDIVE_CHAT_API_URL
      ? window.KDIVE_CHAT_API_URL
      : process.env.NEXT_PUBLIC_SURFY_CHAT_API_URL || DEFAULT_CHAT_API_URL
  );
  const baseUrl = chatUrl.replace(/\/api\/chat\/?$/, '');
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  return `${baseUrl}${normalizedPath}`;
}
