'use client';

import { useMemo } from 'react';
import { getRecommendedPlaces, FOOD_RESULT_LIMIT, getPlaceKey } from '@/data/albums';
import { useKdive } from '@/store/KdiveContext';

export default function PlaceDetail({ place, album }) {
  const { likedPlaceKeys, showFood } = useKdive();

  const likedCount = useMemo(() => {
    if (!album) return 0;
    return getRecommendedPlaces(album).filter((p) => likedPlaceKeys.has(getPlaceKey(album.id, p.name))).length;
  }, [album, likedPlaceKeys]);

  if (!place) return null;

  const vibeTagText = `${place.category === 'must' ? '필수 명소' : '음악 키워드'} — ${album?.vibe || ''}`;
  const moreFoodLabel = likedCount > 0 ? `맛집 더 알아보기 (${FOOD_RESULT_LIMIT}개) →` : '관광지를 좋아요 해주세요';

  return (
    <div className="min-w-0 flex flex-col gap-[14px]">
      <div className="bg-surface border border-[rgba(0,0,0,0.08)] rounded-[14px] py-6 px-6">
        <div className="text-[11px] tracking-[0.1em] uppercase text-muted mb-[5px]">선택된 장소</div>
        <div className="font-serif text-[1.4rem]">{place.name}</div>
      </div>
      <div className="bg-surface border border-[rgba(0,0,0,0.08)] rounded-[14px] py-6 px-6 flex-1 min-h-[190px]">
        <div className="text-[11px] tracking-[0.1em] uppercase text-accent mb-[10px] flex items-center gap-[6px]">
          <span className="block w-[6px] h-[6px] rounded-full bg-accent flex-shrink-0" />
          큐레이션
        </div>
        <span className="inline-flex items-center gap-[5px] bg-accent-soft border border-accent-border text-accent text-[12px] px-[10px] py-1 rounded-full mb-[10px]">
          {vibeTagText}
        </span>
        <p className="text-[13px] text-black/60 leading-[1.7]">{place.desc}</p>
      </div>
      <button
        type="button"
        onClick={showFood}
        disabled={likedCount === 0}
        className={`w-full py-[13px] bg-white border border-[rgba(0,0,0,0.08)] rounded-[13px] font-pretendard text-[13px] font-medium cursor-pointer transition-all flex items-center justify-center gap-[6px] ${
          likedCount === 0 ? 'cursor-not-allowed text-muted bg-surface' : 'text-text hover:shadow-[0_4px_14px_rgba(0,0,0,0.04)]'
        }`}
      >
        {moreFoodLabel}
      </button>
    </div>
  );
}
