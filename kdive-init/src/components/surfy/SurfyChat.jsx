'use client';

import { useEffect, useRef, useState } from 'react';
import { ALBUMS } from '@/data/albums';
import { useKdive } from '@/store/KdiveContext';
import { useSurfyChat } from './surfyChatStore';

export default function SurfyChat() {
  const { activeChat, sendUserMessage, handleSuggestionClick } = useSurfyChat();
  const { activeAlbum, currentIdx, likedPlaceKeys } = useKdive();
  const conversationRef = useRef(null);
  const [draft, setDraft] = useState('');
  const [tripMode, setTripMode] = useState('Before trip');

  // 새 메시지가 추가되면 자동 스크롤
  useEffect(() => {
    if (conversationRef.current) {
      conversationRef.current.scrollTop = conversationRef.current.scrollHeight;
    }
  }, [activeChat?.messages?.length]);

  const buildUserContext = () => {
    const album = activeAlbum || ALBUMS[currentIdx];
    const musicKeywords = album?.vibe ? album.vibe.split('·').map((k) => k.trim()).filter(Boolean) : [];
    return {
      music_keywords: musicKeywords,
      liked_places: Array.from(likedPlaceKeys).slice(0, 10).map((key) => ({ key })),
      extras: {
        trip_mode: tripMode,
        active_track: album ? { title: album.title, artist: album.artist, vibe: album.vibe } : null,
      },
    };
  };

  const onSubmit = (event) => {
    event.preventDefault();
    if (!draft.trim()) return;
    sendUserMessage(draft, buildUserContext());
    setDraft('');
  };

  return (
    <section
      className="w-full h-[calc(100vh-61px)] min-h-0 border-0 rounded-none bg-transparent shadow-none grid overflow-hidden"
      style={{ gridTemplateRows: 'auto minmax(0,1fr) auto' }}
      aria-label="Surfy 대화"
    >
      <header className="min-h-[104px] pt-[30px] pb-[18px] border-b-0 flex items-center justify-between gap-[18px] max-[768px]:py-[18px] max-[760px]:flex-col max-[760px]:items-start">
        <div className="min-w-0">
          <p className="text-accent text-[12px] font-bold tracking-[0.12em] uppercase mb-[6px]">Surfy</p>
          <h1 className="font-pretendard text-[22px] leading-[1.2] max-[768px]:text-[18px]">
            What travel spots should we explore?
          </h1>
        </div>
        <label className="min-w-[158px] h-[38px] border border-[rgba(0,0,0,0.08)] rounded-full bg-white flex items-center gap-2 pl-[14px] pr-[10px] text-muted text-[11px] font-bold whitespace-nowrap max-[760px]:self-end">
          <span>Trip mode</span>
          <select
            value={tripMode}
            onChange={(e) => setTripMode(e.target.value)}
            aria-label="여행 상태 선택"
            className="min-w-0 border-0 outline-0 bg-transparent text-text font-pretendard text-[12px] font-bold cursor-pointer"
          >
            <option>Before trip</option>
            <option>During trip</option>
          </select>
        </label>
      </header>

      <div ref={conversationRef} className="min-h-0 overflow-y-auto overflow-x-hidden py-[18px] pb-7 flex flex-col gap-[18px] scrollbar-thin">
        {activeChat?.messages.map((message, idx) => {
          if (message.kind === 'suggestions') {
            return (
              <div
                key={`suggestion-${idx}`}
                className="grid grid-cols-3 gap-[10px] w-[min(680px,100%)] ml-[46px] max-[900px]:grid-cols-1 max-[900px]:ml-0"
                aria-label="장소 제안"
              >
                {message.cards.map((card) => (
                  <button
                    key={card.name}
                    type="button"
                    onClick={() => handleSuggestionClick(card.name)}
                    className="min-h-[132px] border border-[rgba(0,0,0,0.08)] rounded-[18px] bg-white p-[18px] text-left cursor-pointer transition-all hover:border-accent-border hover:shadow-[0_12px_28px_rgba(0,168,232,0.08)] hover:-translate-y-[2px] max-[768px]:min-h-[96px]"
                  >
                    <span className="inline-flex h-[24px] px-[10px] rounded-full bg-accent-soft text-accent-dark items-center text-[11px] font-bold mb-[34px]">
                      {card.tag}
                    </span>
                    <strong className="block text-[15px] leading-[1.35]">{card.name}</strong>
                  </button>
                ))}
              </div>
            );
          }
          const isUser = message.role === 'user';
          return (
            <article
              key={`msg-${idx}`}
              className={`flex items-end gap-3 ${isUser ? 'self-end' : 'self-start'} ${message.wide ? 'max-w-[88%]' : 'max-w-[76%]'} max-[768px]:max-w-full`}
            >
              {!isUser && <span className="kd-surfy-avatar" aria-hidden="true" />}
              <div
                className={`rounded-[18px] py-[15px] px-[17px] text-[14px] leading-[1.6] ${isUser ? 'bg-accent text-white' : 'bg-[#f6f6f6] text-text'} ${message.loading ? 'kd-surfy-loading' : ''}`}
              >
                <p>{message.content}</p>
              </div>
            </article>
          );
        })}
      </div>

      <form
        onSubmit={onSubmit}
        className="w-full min-h-[58px] mt-auto mb-6 rounded-[20px] bg-white border border-[rgba(0,0,0,0.08)] py-[10px] pl-7 pr-[18px] shadow-[0_12px_30px_rgba(0,0,0,0.05)] flex items-center"
      >
        <input
          type="text"
          aria-label="자연어 검색"
          placeholder="Type here to explore places or restaurants"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          className="flex-1 min-w-0 border-0 outline-0 bg-transparent text-text font-pretendard text-[14px] font-semibold h-[38px] placeholder:text-muted placeholder:opacity-100"
        />
        <button
          type="submit"
          aria-label="검색 보내기"
          className="w-[38px] h-[38px] border-0 rounded-full bg-accent text-white text-[16px] font-bold leading-none cursor-pointer"
        >
          ↗
        </button>
      </form>
    </section>
  );
}
