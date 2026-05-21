'use client';

import { useCallback, useEffect, useState } from 'react';
import { getSurfyApiUrl } from '@/utils/surfyApi';

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

const SURFY_CHAT_API_URL = getSurfyApiUrl('/api/chat/');

const AGENT_STATUS_MESSAGES = [
  'Getting a feel for your travel style and request.',
  'Matching you with the right local guide.',
];
const AGENT_DISPLAY_LABELS = {
  // 내부 routing은 restaurant이지만, 사용자에게는 한국 맛집 전문가 Foodie로 보여준다.
  restaurant: { name: 'Foodie', role: 'your Korean food guide' },
  // Tourist Agent는 사용자가 아니라 장소를 찾아주는 가이드처럼 보이도록 Local Scout로 표시한다.
  tourist: { name: 'Local Scout', role: 'your sightseeing guide' },
  // Event Agent는 전시/팝업/공연을 잘 아는 현지 문화 큐레이터 느낌으로 표시한다.
  event: { name: 'Culture Insider', role: 'your event guide' },
};

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

// 서버 응답 전까지 보여줄 status preview 전용 키워드다.
// 실제 agent 라우팅은 backend supervisor/LangGraph 결과를 따른다.
const STATUS_PREVIEW_RESTAURANT_HINTS_KO = ['맛집', '식당', '밥', '카페', '커피', '브런치', '디저트', '한식', '일식', '중식', '양식'];
const STATUS_PREVIEW_RESTAURANT_HINTS_EN = ['restaurant', 'food', 'meal', 'eat', 'cafe', 'coffee', 'brunch', 'dessert', 'korean food', 'japanese food', 'chinese food', 'western food'];
const STATUS_PREVIEW_RESTAURANT_HINTS = [...STATUS_PREVIEW_RESTAURANT_HINTS_KO, ...STATUS_PREVIEW_RESTAURANT_HINTS_EN];

const STATUS_PREVIEW_EXPLICIT_TOUR_HINTS_KO = ['관광', '관광지', '여행지', '명소', '가볼만', '구경', '산책', '박물관', '공원'];
const STATUS_PREVIEW_EXPLICIT_TOUR_HINTS_EN = ['tour', 'sightseeing', 'landmark', 'attraction', 'place to visit', 'walk', 'museum', 'park'];
const STATUS_PREVIEW_EXPLICIT_TOUR_HINTS = [...STATUS_PREVIEW_EXPLICIT_TOUR_HINTS_KO, ...STATUS_PREVIEW_EXPLICIT_TOUR_HINTS_EN];

const STATUS_PREVIEW_TOUR_HINTS = [...STATUS_PREVIEW_EXPLICIT_TOUR_HINTS, '볼거리', 'things to do'];
const STATUS_PREVIEW_EVENT_HINTS_KO = ['전시', '전시회', '팝업', '이벤트', '공연', '콘서트', '페스티벌', '행사'];
const STATUS_PREVIEW_EVENT_HINTS_EN = ['exhibition', 'popup', 'pop-up', 'event', 'performance', 'concert', 'festival', 'show'];
const STATUS_PREVIEW_EVENT_HINTS = [...STATUS_PREVIEW_EVENT_HINTS_KO, ...STATUS_PREVIEW_EVENT_HINTS_EN];

const buildStatusMessages = (text) => {
  const hasRestaurant = STATUS_PREVIEW_RESTAURANT_HINTS.some((hint) => text.includes(hint));
  const hasEvent = STATUS_PREVIEW_EVENT_HINTS.some((hint) => text.includes(hint));
  const hasExplicitTour = STATUS_PREVIEW_EXPLICIT_TOUR_HINTS.some((hint) => text.includes(hint));
  const hasTour = STATUS_PREVIEW_TOUR_HINTS.some((hint) => text.includes(hint)) && (!hasEvent || hasExplicitTour);
  const guides = [
    hasRestaurant ? AGENT_DISPLAY_LABELS.restaurant : null,
    hasTour ? AGENT_DISPLAY_LABELS.tourist : null,
    hasEvent ? AGENT_DISPLAY_LABELS.event : null,
  ].filter(Boolean);
  const matchingLabel = guides.length ? formatGuideMatch(guides) : 'the right local guide';
  const activeLabel = guides.length ? formatGuideNames(guides) : 'Your local guide';
  const verb = guides.length > 1 ? 'are' : 'is';
  return [
    AGENT_STATUS_MESSAGES[0],
    `Matching you with ${matchingLabel}.`,
    `${activeLabel} ${verb} curating travel-friendly picks.`,
  ];
};

const formatGuideMatch = (guides) => joinEnglishList(guides.map((guide) => `${guide.name}, ${guide.role}`));

const formatGuideNames = (guides) => joinEnglishList(guides.map((guide) => guide.name));

const joinEnglishList = (items) => {
  if (items.length <= 1) return items[0] || '';
  if (items.length === 2) return items.join(' and ');
  return `${items.slice(0, -1).join(', ')}, and ${items.at(-1)}`;
};

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

  const updateMessage = useCallback((messageId, patch) => {
    _state = {
      ..._state,
      chats: _state.chats.map((c) => {
        if (c.id !== _state.activeChatId) return c;
        const messages = c.messages.map((message) => (message.id === messageId ? { ...message, ...patch } : message));
        return { ...c, messages, preview: patch.content?.slice(0, 32) || c.preview };
      }),
    };
    notify();
  }, []);

  const sendUserMessage = useCallback(async (text, userContext) => {
    if (!text?.trim()) return;
    appendMessage({ role: 'user', kind: 'text', content: text.trim() });
    const history = state.chats.find((c) => c.id === state.activeChatId)?.messages.filter((m) => m.kind === 'text') || [];
    const statusId = `agent-status-${Date.now()}`;
    const statusMessages = buildStatusMessages(text);
    const request = fetch(SURFY_CHAT_API_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: text,
        user_context: userContext,
        history: history.map(({ role, content }) => ({ role, content })),
      }),
    });

    try {
      appendMessage({
        id: statusId,
        role: 'assistant',
        kind: 'status',
        content: statusMessages[0],
        wide: true,
        loading: true,
      });
      for (const content of statusMessages.slice(1)) {
        await wait(420);
        updateMessage(statusId, { content });
      }

      const response = await request;
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data?.detail || 'request_failed');
      updateMessage(statusId, {
        kind: 'text',
        content: data?.response || '응답을 받았지만 표시할 내용이 없어요.',
        wide: true,
        loading: false,
      });
      if (Array.isArray(data?.recommendations) && data.recommendations.length) {
        appendMessage({
          role: 'assistant',
          kind: 'agent_recommendations',
          cards: data.recommendations.slice(0, 3),
          wide: true,
        });
      }
    } catch (e) {
      const detail = e instanceof Error ? e.message : '';
      const content = detail && detail !== 'request_failed'
        ? `Agent 요청 중 오류가 발생했어요: ${detail}`
        : 'Agent server is not ready yet. Please run the backend server from README.md, then try again.';

      updateMessage(statusId, {
        kind: 'text',
        content,
        wide: true,
        loading: false,
      });
    }
  }, [appendMessage, state.activeChatId, state.chats, updateMessage]);

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
