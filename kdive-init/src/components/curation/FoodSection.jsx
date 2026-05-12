'use client';

import { useMemo, useState } from 'react';
import {
  FOOD_RESULT_LIMIT,
  FOOD_TYPES,
  createFoodSuggestionsForPlace,
  getPlaceKey,
  getRecommendedPlaces,
} from '@/data/albums';
import { useKdive } from '@/store/KdiveContext';

export default function FoodSection() {
  const { activeAlbum, foodVisible, likedPlaceKeys, likedFoodKeys, toggleFoodLike, showAuth } = useKdive();
  const [activeFoodKey, setActiveFoodKey] = useState(null);

  const sourcePlaces = useMemo(() => {
    if (!activeAlbum) return [];
    return getRecommendedPlaces(activeAlbum).filter((p) => likedPlaceKeys.has(getPlaceKey(activeAlbum.id, p.name)));
  }, [activeAlbum, likedPlaceKeys]);

  const suggestions = useMemo(() => {
    if (!activeAlbum || !sourcePlaces.length) return [];
    const perPlace = sourcePlaces.map((place) => createFoodSuggestionsForPlace(activeAlbum, place));
    const mixed = [];
    for (let typeIndex = 0; typeIndex < FOOD_TYPES.length && mixed.length < FOOD_RESULT_LIMIT; typeIndex += 1) {
      perPlace.forEach((arr) => {
        if (mixed.length < FOOD_RESULT_LIMIT && arr[typeIndex]) mixed.push(arr[typeIndex]);
      });
    }
    return mixed;
  }, [activeAlbum, sourcePlaces]);

  if (!foodVisible || !activeAlbum) return null;

  return (
    <section
      id="foodSection"
      className="grid gap-5 mt-[30px] w-[min(1160px,calc(100%-clamp(48px,6vw,96px)))] mx-auto scroll-mt-[140px] max-[768px]:w-full max-[768px]:grid-cols-1"
      style={{ gridTemplateColumns: 'minmax(0,1fr) minmax(0,1fr)' }}
      aria-hidden="false"
    >
      <div className="min-w-0 rounded-[20px] overflow-hidden bg-white border border-[rgba(0,0,0,0.08)] min-h-[520px] flex items-center justify-center max-[768px]:min-h-[360px]">
        <div className="flex flex-col items-center gap-[10px] text-muted">
          <div className="text-[36px]">🍜</div>
          <p className="text-[13px]">근처 맛집 지도</p>
        </div>
      </div>
      <div className="kd-food-list min-w-0 flex flex-col gap-[14px] max-h-[520px] overflow-y-auto py-1 pr-2 max-[768px]:max-h-[360px]">
        {suggestions.map((item) => {
          const isActive = activeFoodKey === item.key;
          const isLiked = likedFoodKeys.has(item.key);
          return (
            <article
              key={item.key}
              className={`kd-food-card relative w-full font-pretendard min-h-[76px] border rounded-[14px] bg-white p-0 flex flex-col text-left overflow-hidden cursor-pointer ${isActive ? 'active border-accent' : 'border-[rgba(0,0,0,0.08)]'} hover:border-accent`}
              onClick={() => setActiveFoodKey((prev) => (prev === item.key ? null : item.key))}
            >
              <button
                type="button"
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  toggleFoodLike(item.key);
                }}
                aria-pressed={isLiked}
                aria-label={`${item.title} ${isLiked ? '좋아요 취소' : '좋아요'}`}
                className={`absolute top-[38px] right-[14px] z-[2] w-7 h-7 -translate-y-1/2 rounded-full border bg-white text-heart text-[16px] leading-none flex items-center justify-center cursor-pointer transition-all hover:scale-[1.08] hover:border-heart ${isLiked ? 'border-heart' : 'border-[rgba(0,0,0,0.08)]'}`}
              >
                {isLiked ? '♥' : '♡'}
              </button>
              <div
                role="button"
                className="w-full min-h-[76px] border-0 bg-transparent font-pretendard pl-[18px] pr-[58px] py-[15px] flex flex-col justify-center gap-1 text-left cursor-pointer"
              >
                <span className="text-[11px] text-accent font-semibold">{item.placeName}</span>
                <strong className="text-[14px] font-bold text-text">{item.title}</strong>
                <span className="text-[12px] text-black/55 font-normal leading-[1.45]">{item.desc}</span>
              </div>
              <div className="kd-food-card-detail">
                <div className="min-h-[132px] overflow-hidden pb-[2px] flex flex-col justify-center">
                  <div className="text-[10px] tracking-[0.1em] uppercase text-accent mb-[6px]">
                    {item.placeName} 큐레이션
                  </div>
                  <p className="text-[12px] text-black/60 leading-[1.6]">{item.curation}</p>
                </div>
              </div>
            </article>
          );
        })}
        <button
          type="button"
          onClick={showAuth}
          className="w-full min-h-[52px] border border-[rgba(0,0,0,0.08)] rounded-[14px] bg-white text-text font-pretendard text-[13px] font-semibold cursor-pointer transition-all hover:shadow-[0_4px_14px_rgba(0,0,0,0.04)]"
        >
          더 많은 장소를 탐색하고 싶다면?
        </button>
      </div>
    </section>
  );
}
