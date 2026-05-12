'use client';

import { useCallback, useEffect, useState } from 'react';

// 원본 SURFY 프로토타입 대화. 메시지는 객체 배열로 보관.
const SURFY_PROTOTYPE_MESSAGES = [
  { role: 'assistant', kind: 'text', content: '좋아요. 지금 위치를 기준으로 가까운 대안을 찾아볼게요.' },
  { role: 'user', kind: 'text', content: '지금 가고 싶던 카페가 영업을 안 해서, 근처에 갈 만한 다른 카페를 추천해줘.' },
  {
    role: 'assistant', kind: 'suggestions',
    cards: [
      { tag: 'Open now', name: 'Layered Yeonnam' },
      { tag: 'Quiet', name: 'Anthracite Hapjeong' },
      { tag: 'Dessert', name: 'Cheongsudang Gongmyeong' },
    ],
  },
  {
    role: 'assistant', kind: 'text',
    content: '근처에서 바로 이동하기 좋은 카페를 우선으로 추천할게요. 영업 중인 곳, 도보 이동이 쉬운 곳, 그리고 산뜻한 분위기의 공간을 함께 볼 수 있어요.',
    wide: true,
  },
];

const SURFY_CAFE_CURATIONS = {
  'Layered Yeonnam': 'Layered Yeonnam은 디저트와 차를 가볍게 즐기기 좋은 대안이에요. 연남동 안에서 이동 부담이 적고, 밝은 분위기라 갑자기 카페를 바꿔야 할 때도 실패 확률이 낮아요.',
  'Anthracite Hapjeong': 'Anthracite Hapjeong은 조금 더 조용하고 오래 머물기 좋은 선택이에요. 대화하거나 다음 일정을 정리하기 좋고, 커피 중심의 차분한 무드가 필요할 때 잘 맞아요.',
  'Cheongsudang Gongmyeong': 'Cheongsudang Gongmyeong은 디저트와 공간 분위기를 함께 보고 싶을 때 좋아요. 사진을 남기기 좋은 요소가 있고, 짧은 휴식 코스로 넣기에도 자연스러워요.',
};

const SURFY_CHAT_API_URL = typeof window !== 'undefined' && window.KDIVE_CHAT_API_URL
  ? window.KDIVE_CHAT_API_URL
  : 'http://localhost:8000/api/chat/';

const INITIAL_CHATS = [
  { id: 'prototype', title: '채팅 기록 1', preview: '현재 대화 prototype', messages: SURFY_PROTOTYPE_MESSAGES },
];

// 가벼운 in-memory store. 새로고침 시 초기화됨 (원본 동작과 동일).
let _state = {
  chats: INITIAL_CHATS,
  activeChatId: 'prototype',
  newChatCount: 0,
};
const listeners = new Set();

function notify() {
  listeners.forEach((l) => l(_state));
}

export function useSurfyChat() {
  const [state, setState] = useState(_state);

  useEffect(() => {
    const listener = (next) => setState({ ..._state });
    listeners.add(listener);
    return () => listeners.delete(listener);
  }, []);

  const switchChat = useCallback((chatId) => {
    _state = { ..._state, activeChatId: chatId };
    notify();
  }, []);

  const createNewChat = useCallback(() => {
    _state.newChatCount += 1;
    const title = _state.newChatCount === 1 ? '새 대화' : `새 대화 ${_state.newChatCount}`;
    const id = `new-${Date.now()}`;
    _state = {
      ..._state,
      chats: [..._state.chats, { id, title, preview: '자연어로 장소 탐색', messages: [] }],
      activeChatId: id,
    };
    notify();
  }, []);

  const appendMessage = useCallback((message) => {
    _state = {
      ..._state,
      chats: _state.chats.map((c) => (c.id === _state.activeChatId ? { ...c, messages: [...c.messages, message], preview: message.content?.slice(0, 32) || c.preview } : c)),
    };
    notify();
  }, []);

  const replaceLastAssistant = useCallback((content) => {
    _state = {
      ..._state,
      chats: _state.chats.map((c) => {
        if (c.id !== _state.activeChatId) return c;
        const msgs = [...c.messages];
        for (let i = msgs.length - 1; i >= 0; i -= 1) {
          if (msgs[i].role === 'assistant' && msgs[i].loading) {
            msgs[i] = { ...msgs[i], content, loading: false };
            break;
          }
        }
        return { ...c, messages: msgs };
      }),
    };
    notify();
  }, []);

  const sendUserMessage = useCallback(async (text, userContext) => {
    if (!text?.trim()) return;
    appendMessage({ role: 'user', kind: 'text', content: text.trim() });
    const history = state.chats.find((c) => c.id === state.activeChatId)?.messages.filter((m) => m.kind === 'text') || [];
    appendMessage({ role: 'assistant', kind: 'text', content: 'Surfy is thinking...', loading: true, wide: true });
    try {
      const response = await fetch(SURFY_CHAT_API_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: text,
          user_context: userContext,
          history: history.map(({ role, content }) => ({ role, content })),
        }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data?.detail || 'request_failed');
      replaceLastAssistant(data?.response || '응답을 받았지만 표시할 내용이 없어요.');
    } catch (e) {
      replaceLastAssistant('Agent server is not ready yet. Please run the Django server from README.md, then try again.');
    }
  }, [appendMessage, replaceLastAssistant, state.activeChatId, state.chats]);

  const handleSuggestionClick = useCallback((cafeName) => {
    const text = SURFY_CAFE_CURATIONS[cafeName] || `${cafeName}에 대한 큐레이션을 준비하고 있어요.`;
    appendMessage({ role: 'assistant', kind: 'text', content: text, wide: true });
  }, [appendMessage]);

  return {
    chats: state.chats,
    activeChatId: state.activeChatId,
    activeChat: state.chats.find((c) => c.id === state.activeChatId),
    switchChat,
    createNewChat,
    sendUserMessage,
    handleSuggestionClick,
  };
}
