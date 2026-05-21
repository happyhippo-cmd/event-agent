'use client';

/* eslint-disable @next/next/no-img-element */
import { useEffect, useRef, useState } from 'react';
import { ALBUMS } from '@/data/albums';
import { useKdive } from '@/store/KdiveContext';
import { useSurfyChat } from './surfyChatStore';

const getRecommendationKey = (card) => `${card.source_agent || 'agent'}-${card.id || card.kakao_place_id || card.name}`;

const getFallbackEmoji = (card) => {
  if (card.source_agent === 'tourist') return '🏛️';
  if (card.source_agent === 'event') return '🎟️';
  const category = `${card.category || ''} ${card.name || ''}`;
  if (category.includes('카페') || category.includes('커피') || category.includes('찻집')) return '☕';
  return '🍽️';
};

const getAgentPickLabel = (sourceAgent) => {
  if (sourceAgent === 'tourist') return 'Local Scout pick';
  if (sourceAgent === 'event') return 'Culture Insider pick';
  return 'Foodie pick';
};

const getAgentSectionTitle = (sourceAgent) => {
  if (sourceAgent === 'tourist') return 'Local Scout';
  if (sourceAgent === 'event') return 'Culture Insider';
  return 'Foodie';
};

const getAgentSectionRole = (sourceAgent) => {
  if (sourceAgent === 'tourist') return 'Sightseeing guide';
  if (sourceAgent === 'event') return 'Event guide';
  return 'Korean food guide';
};

const getRecommendationGroups = (message) => {
  if (Array.isArray(message.groups) && message.groups.length) {
    return message.groups
      .map((group) => ({
        source_agent: group.source_agent,
        label: group.label || getAgentSectionTitle(group.source_agent),
        role: group.role || getAgentSectionRole(group.source_agent),
        cards: Array.isArray(group.cards) ? group.cards : [],
      }))
      .filter((group) => group.cards.length);
  }

  const groups = [];
  const groupIndex = {};
  for (const card of message.cards || []) {
    const sourceAgent = card.source_agent || 'restaurant';
    if (!groupIndex[sourceAgent]) {
      groupIndex[sourceAgent] = {
        source_agent: sourceAgent,
        label: getAgentSectionTitle(sourceAgent),
        role: getAgentSectionRole(sourceAgent),
        cards: [],
      };
      groups.push(groupIndex[sourceAgent]);
    }
    groupIndex[sourceAgent].cards.push(card);
  }
  return groups;
};

export default function SurfyChat() {
  const { activeChat, sendUserMessage, handleSuggestionClick } = useSurfyChat();
  const {
    activeAlbum,
    currentIdx,
    likedTrackIds,
    likedPlaceKeys,
    likedPlaceRecords,
    likedFoodKeys,
    likedFoodRecords,
  } = useKdive();
  const conversationRef = useRef(null);
  const [draft, setDraft] = useState('');
  const [tripMode, setTripMode] = useState('Before trip');
  const [expandedCurationKey, setExpandedCurationKey] = useState(null);
  const [imageErrorKeys, setImageErrorKeys] = useState(() => new Set());

  // 새 메시지가 추가되면 자동 스크롤
  useEffect(() => {
    if (conversationRef.current) {
      conversationRef.current.scrollTop = conversationRef.current.scrollHeight;
    }
  }, [activeChat?.messages]);

  const buildUserContext = () => {
    const album = activeAlbum || ALBUMS[currentIdx];
    const likedAlbums = ALBUMS.filter((item) => likedTrackIds.has(item.id));
    const keywordAlbums = likedAlbums.length ? likedAlbums : [album].filter(Boolean);
    const musicKeywords = Array.from(new Set(keywordAlbums.flatMap((item) => (
      item?.vibe ? item.vibe.split('·').map((k) => k.trim()).filter(Boolean) : []
    ))));
    const nameFromKey = (key) => key.split('::')[1] || key;
    const foodNameFromKey = (key) => {
      const parts = key.split('::');
      return [parts[1], parts[2]].filter(Boolean).join(' ');
    };
    return {
      music_keywords: musicKeywords,
      liked_places: Array.from(likedPlaceKeys).slice(0, 10).map((key) => ({
        key,
        name: likedPlaceRecords[key]?.name || nameFromKey(key),
        category: likedPlaceRecords[key]?.category || '관광지',
        keyword: likedPlaceRecords[key]?.source_keyword,
        lat: likedPlaceRecords[key]?.lat,
        lng: likedPlaceRecords[key]?.lng,
        address: likedPlaceRecords[key]?.address,
      })),
      liked_foods: Array.from(likedFoodKeys).slice(0, 10).map((key) => ({
        key,
        name: likedFoodRecords[key]?.title || likedFoodRecords[key]?.name || foodNameFromKey(key),
        category: likedFoodRecords[key]?.genre || likedFoodRecords[key]?.category || '맛집',
      })),
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

  const toggleCuration = (cardKey) => {
    setExpandedCurationKey((current) => (current === cardKey ? null : cardKey));
  };

  const markImageError = (cardKey) => {
    setImageErrorKeys((current) => new Set([...current, cardKey]));
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
          if (message.kind === 'status') {
            return (
              <article
                key={message.id || `status-${idx}`}
                className="self-start max-w-[76%] max-[768px]:max-w-full flex items-end gap-3"
              >
                <span className="kd-surfy-avatar" aria-hidden="true" />
                <div className="rounded-[8px] py-[10px] px-[13px] text-[12px] leading-[1.5] bg-accent-soft text-accent-dark border border-accent-border">
                  <p>{message.content}</p>
                </div>
              </article>
            );
          }
          if (message.kind === 'suggestions') {
            return (
              <div
                key={message.id || `suggestion-${idx}`}
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
          if (message.kind === 'agent_recommendations') {
            const groups = getRecommendationGroups(message);
            return (
              <div
                key={message.id || `agent-recommendations-${idx}`}
                className="w-[min(920px,100%)] ml-[46px] flex flex-col gap-[18px] max-[980px]:ml-0"
                aria-label="추천 장소"
              >
                {groups.map((group, groupIdx) => (
                  <section key={`${group.source_agent || 'agent'}-${groupIdx}`} className="flex flex-col gap-[10px]">
                    <div className="flex items-baseline gap-[8px] min-w-0">
                      <strong className="text-[13px] leading-[1.35] text-text">{group.label}</strong>
                      <span className="text-[11px] leading-[1.35] text-black/45">{group.role}</span>
                    </div>
                    <div className="grid grid-cols-3 gap-[10px] max-[980px]:grid-cols-1">
                      {group.cards.map((card) => {
                        const cardKey = getRecommendationKey(card);
                        const hasPhoto = card.photo_url && !imageErrorKeys.has(cardKey);
                        const isExpanded = expandedCurationKey === cardKey;
                        return (
                          <article
                            key={cardKey}
                            className="min-h-[286px] border border-[rgba(0,0,0,0.08)] rounded-[8px] bg-white p-[14px] text-left flex flex-col gap-[10px] shadow-[0_10px_24px_rgba(0,0,0,0.04)]"
                          >
                            <button
                              type="button"
                              onClick={() => toggleCuration(cardKey)}
                              aria-expanded={isExpanded}
                              aria-label={`${card.name} 큐레이션 보기`}
                              className="relative w-full aspect-[16/10] overflow-hidden rounded-[8px] border border-[rgba(0,0,0,0.06)] bg-[#f6f6f6] cursor-pointer"
                            >
                              {hasPhoto ? (
                                <img
                                  src={card.photo_url}
                                  alt=""
                                  onError={() => markImageError(cardKey)}
                                  className="absolute inset-0 w-full h-full object-cover"
                                />
                              ) : (
                                <span className="absolute inset-0 flex items-center justify-center text-[34px] bg-accent-soft" aria-hidden="true">
                                  {getFallbackEmoji(card)}
                                </span>
                              )}
                            </button>
                            {isExpanded ? (
                              <p className="text-[12px] text-black/65 leading-[1.6] rounded-[8px] bg-[#f8fbfc] border border-accent-border px-[11px] py-[10px]">
                                {card.curation || card.ranking_basis || '큐레이션을 준비하고 있어요.'}
                              </p>
                            ) : null}
                            <div className="min-w-0">
                              <div className="text-[11px] text-accent font-bold leading-[1.3] mb-[5px]">
                                {[getAgentPickLabel(card.source_agent), card.area || card.gu, card.category].filter(Boolean).join(' · ')}
                              </div>
                              <strong className="block text-[15px] leading-[1.35] text-text">{card.name}</strong>
                            </div>
                            <p className="text-[12px] text-black/55 leading-[1.5] min-h-[36px]">{card.address || '주소 정보 준비 중'}</p>
                            <div className="flex flex-wrap gap-[6px] mt-auto">
                              {card.rating ? <span className="h-[24px] px-[8px] rounded-full bg-[#f6f6f6] text-[11px] text-text flex items-center">평점 {card.rating}</span> : null}
                              {card.review_count ? <span className="h-[24px] px-[8px] rounded-full bg-[#f6f6f6] text-[11px] text-text flex items-center">리뷰 {card.review_count}</span> : null}
                              {card.distance_km ? <span className="h-[24px] px-[8px] rounded-full bg-[#f6f6f6] text-[11px] text-text flex items-center">거리 {card.distance_km}km</span> : null}
                              {card.matched_preferences?.slice(0, 2).map((tag) => (
                                <span key={tag} className="h-[24px] px-[8px] rounded-full bg-accent-soft text-[11px] text-accent-dark flex items-center">{tag}</span>
                              ))}
                            </div>
                          </article>
                        );
                      })}
                    </div>
                  </section>
                ))}
              </div>
            );
          }
          const isUser = message.role === 'user';
          return (
            <article
              key={message.id || `msg-${idx}`}
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
