'use client';

import { useMemo, useState } from 'react';
import {
  ALBUMS,
  createFoodSuggestionsForPlace,
  getPlaceKey,
  getRecommendedPlaces,
} from '@/data/albums';
import { useKdive } from '@/store/KdiveContext';

const TABS = [
  { id: 'liked', label: 'Liked' },
  { id: 'cluster', label: '지역 클러스터' },
  { id: 'places', label: '관광지' },
  { id: 'foods', label: '맛집' },
  { id: 'events', label: '전시/팝업' },
];

function buildHistoryItems(likedTrackIds, likedPlaceKeys, likedFoodKeys) {
  const tracks = ALBUMS
    .filter((album) => likedTrackIds.has(album.id))
    .map((album) => ({
      key: `track-${album.id}`,
      type: 'track',
      label: 'Keyword',
      album,
      title: album.vibe,
      subtitle: 'K-Dive mood keyword',
      emoji: '♡',
    }));

  const places = [];
  const foods = [];

  ALBUMS.forEach((album) => {
    getRecommendedPlaces(album).forEach((place) => {
      const key = getPlaceKey(album.id, place.name);
      if (likedPlaceKeys.has(key)) {
        places.push({
          key: `place-${key}`,
          rawKey: key,
          type: 'place',
          label: place.category === 'must' ? '필수 명소' : '관광지',
          album,
          place,
          title: place.name,
          subtitle: album.title,
          emoji: place.emoji,
        });
      }

      createFoodSuggestionsForPlace(album, place).forEach((food) => {
        if (likedFoodKeys.has(food.key)) {
          foods.push({
            key: `food-${food.key}`,
            rawKey: food.key,
            type: 'food',
            label: '맛집',
            album,
            food,
            title: food.title,
            subtitle: food.placeName,
            emoji: '🍜',
          });
        }
      });
    });
  });

  return { tracks, places, foods };
}

function EmptyCard({ index }) {
  return (
    <div
      aria-hidden="true"
      className="min-h-[260px] rounded-[16px] border border-[rgba(0,0,0,0.1)] bg-white shadow-[3px_5px_6px_rgba(0,0,0,0.16)] max-[900px]:min-h-[220px]"
    >
      <span className="sr-only">empty history slot {index + 1}</span>
    </div>
  );
}

function HistoryCard({ item, onUnlike }) {
  return (
    <article className="group relative min-h-[260px] overflow-hidden rounded-[16px] border border-[rgba(0,0,0,0.1)] bg-white shadow-[3px_5px_6px_rgba(0,0,0,0.16)] transition-transform duration-200 hover:-translate-y-1 max-[900px]:min-h-[220px]">
      <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 bg-white">
        <span className="text-[40px]">{item.emoji}</span>
        <span className="px-4 text-center text-[13px] text-muted">{item.label}</span>
      </div>

      <div className="absolute bottom-4 left-4 right-4 text-text">
        <div className="mb-2 text-[10px] font-bold uppercase tracking-[0.12em] text-accent">
          {item.label}
        </div>
        <h3 className="truncate font-serif text-[24px] leading-tight">{item.title}</h3>
        <p className="mt-1 truncate text-[12px] text-muted">{item.subtitle}</p>
      </div>

      <button
        type="button"
        onClick={() => onUnlike(item)}
        aria-label={`${item.title} 좋아요 취소`}
        className="absolute bottom-5 right-5 flex h-9 w-9 items-center justify-center rounded-full border border-white bg-white text-[24px] leading-none text-heart shadow-[0_4px_14px_rgba(0,0,0,0.12)] transition-transform hover:scale-105"
      >
        ♥
      </button>
    </article>
  );
}

function ComingSoonCard({ label }) {
  return (
    <div className="min-h-[260px] rounded-[16px] border border-[rgba(0,0,0,0.1)] bg-white p-6 shadow-[3px_5px_6px_rgba(0,0,0,0.16)] max-[900px]:min-h-[220px]">
      <div className="flex h-full flex-col justify-between">
        <span className="text-[11px] font-bold uppercase tracking-[0.12em] text-accent">{label}</span>
        <p className="text-[13px] leading-[1.6] text-muted">
          온보딩에서 저장한 기록을 바탕으로 채워질 영역이에요.
        </p>
      </div>
    </div>
  );
}

export default function HistoryPage() {
  const {
    loggedIn,
    activeAppPage,
    likedTrackIds,
    likedPlaceKeys,
    likedFoodKeys,
    toggleTrackLike,
    togglePlaceLike,
    toggleFoodLike,
  } = useKdive();
  const [activeTab, setActiveTab] = useState('liked');

  const items = useMemo(
    () => buildHistoryItems(likedTrackIds, likedPlaceKeys, likedFoodKeys),
    [likedTrackIds, likedPlaceKeys, likedFoodKeys]
  );

  if (!loggedIn || activeAppPage !== 'history') return null;

  const visibleItems = (() => {
    if (activeTab === 'places') return items.places;
    if (activeTab === 'foods') return items.foods;
    if (activeTab === 'liked') return [...items.tracks, ...items.places, ...items.foods];
    return [];
  })();

  const placeholderCount = Math.max(0, 10 - visibleItems.length);
  const isFutureTab = activeTab === 'cluster' || activeTab === 'events';

  const handleUnlike = (item) => {
    if (item.type === 'track') toggleTrackLike(item.album.id);
    if (item.type === 'place') togglePlaceLike(item.album.id, item.place.name);
    if (item.type === 'food') toggleFoodLike(item.food.key);
  };

  return (
    <section id="historyPage" className="min-h-screen bg-white pt-[112px] max-[760px]:pt-[92px]">
      <div className="mx-auto flex w-[min(1360px,calc(100%-64px))] flex-col gap-[72px] max-[760px]:w-[calc(100%-32px)] max-[760px]:gap-10">
        <div className="flex flex-wrap justify-center gap-5 max-[760px]:gap-3">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              className={`min-w-[112px] border-0 px-8 py-4 text-[20px] font-bold transition-colors max-[760px]:min-w-0 max-[760px]:px-4 max-[760px]:py-3 max-[760px]:text-[14px] ${
                activeTab === tab.id ? 'bg-accent text-white' : 'bg-[#d9d9d9] text-text hover:bg-accent-border'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="kd-history-scroll max-h-[calc(100vh-260px)] overflow-y-auto pr-7 max-[760px]:max-h-none max-[760px]:overflow-visible max-[760px]:pr-0">
          <div className="grid grid-cols-5 gap-x-8 gap-y-10 max-[1180px]:grid-cols-4 max-[900px]:grid-cols-3 max-[640px]:grid-cols-2 max-[420px]:grid-cols-1">
            {isFutureTab && <ComingSoonCard label={TABS.find((tab) => tab.id === activeTab)?.label} />}
            {!isFutureTab && visibleItems.map((item) => (
              <HistoryCard key={item.key} item={item} onUnlike={handleUnlike} />
            ))}
            {!isFutureTab && Array.from({ length: placeholderCount }).map((_, index) => (
              <EmptyCard key={`empty-${index}`} index={index} />
            ))}
            {isFutureTab && Array.from({ length: 9 }).map((_, index) => (
              <EmptyCard key={`future-empty-${index}`} index={index} />
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
