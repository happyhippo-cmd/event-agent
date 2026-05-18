'use client';

import { useMemo } from 'react';
import { FOOD_RESULT_LIMIT, MIN_PLACE_SELECTION, getPlaceSelectionKey } from '@/data/albums';
import { useKdive } from '@/store/KdiveContext';

export default function PlaceDetail({ place, album, places = [] }) {
  const { likedPlaceKeys, showFood } = useKdive();

  const likedCount = useMemo(() => {
    if (!album) return 0;
    return places.filter((p) => likedPlaceKeys.has(getPlaceSelectionKey(album.id, p))).length;
  }, [album, likedPlaceKeys, places]);

  if (!place) return null;

  const vibeTagText = `${place.category === 'must' ? '필수 명소' : '음악 키워드'} — ${place.source_keyword || album?.vibe || ''}`;
  const moreFoodLabel = likedCount >= MIN_PLACE_SELECTION
    ? `근처 맛집 ${FOOD_RESULT_LIMIT}개 보기 →`
    : `관광지를 ${MIN_PLACE_SELECTION}곳 이상 선택해주세요 (${likedCount}/${MIN_PLACE_SELECTION})`;

  return (
    <div className="min-w-0 h-[clamp(260px,34vh,360px)] min-h-0 flex flex-col gap-[clamp(8px,1.2vh,12px)] max-[768px]:h-auto">
      <div className="bg-surface border border-[rgba(0,0,0,0.08)] rounded-[14px] py-[clamp(12px,1.6vh,16px)] px-5">
        <div className="text-[11px] tracking-[0.1em] uppercase text-muted mb-[5px]">선택된 장소</div>
        <div className="font-serif text-[clamp(1.2rem,2vw,1.4rem)] leading-tight">{place.name}</div>
      </div>
      <div className="bg-surface border border-[rgba(0,0,0,0.08)] rounded-[14px] py-[clamp(14px,1.8vh,18px)] px-5 flex-1 min-h-0 overflow-y-auto">
        <div className="text-[11px] tracking-[0.1em] uppercase text-accent mb-2 flex items-center gap-[6px]">
          <span className="block w-[6px] h-[6px] rounded-full bg-accent flex-shrink-0" />
          큐레이션
        </div>
        <span className="inline-flex max-w-full items-center gap-[5px] whitespace-normal bg-accent-soft border border-accent-border text-accent text-[12px] px-[10px] py-1 rounded-full mb-2">
          {vibeTagText}
        </span>
        <p className="text-[12px] text-black/60 leading-[1.6]">{place.curation || place.desc}</p>
      </div>
      <button
        type="button"
        onClick={showFood}
        disabled={likedCount < MIN_PLACE_SELECTION}
        className={`w-full py-[10px] bg-white border border-[rgba(0,0,0,0.08)] rounded-[13px] font-pretendard text-[13px] font-medium cursor-pointer transition-all flex items-center justify-center gap-[6px] ${
          likedCount < MIN_PLACE_SELECTION ? 'cursor-not-allowed text-muted bg-surface' : 'text-text hover:shadow-[0_4px_14px_rgba(0,0,0,0.04)]'
        }`}
      >
        {moreFoodLabel}
      </button>
    </div>
  );
}
