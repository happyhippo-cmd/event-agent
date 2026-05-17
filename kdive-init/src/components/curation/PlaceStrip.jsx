'use client';

import { useRef } from 'react';
import { getPlaceSelectionKey } from '@/data/albums';
import { useKdive } from '@/store/KdiveContext';

export default function PlaceStrip({ places }) {
  const { activeAlbum, selectedPlaceIndex, setSelectedPlaceIndex, likedPlaceKeys, togglePlaceLike } = useKdive();
  const stripRef = useRef(null);

  if (!activeAlbum) return null;

  const scrollStrip = (direction) => {
    const node = stripRef.current;
    if (!node) return;
    node.scrollBy({
      left: direction * Math.max(260, node.clientWidth * 0.75),
      behavior: 'smooth',
    });
  };

  return (
    <div className="relative w-[min(1160px,calc(100%-clamp(48px,6vw,96px)))] mx-auto mb-[clamp(12px,1.8vh,18px)] max-[768px]:w-full">
      {places.length > 4 ? (
        <>
          <button
            type="button"
            onClick={() => scrollStrip(-1)}
            aria-label="이전 관광지 보기"
            className="absolute left-[-14px] top-1/2 z-10 flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-full border border-[rgba(0,0,0,0.08)] bg-white text-[22px] leading-none text-text shadow-[0_6px_18px_rgba(0,0,0,0.08)] transition-transform hover:scale-105 max-[768px]:left-1"
          >
            ‹
          </button>
          <button
            type="button"
            onClick={() => scrollStrip(1)}
            aria-label="다음 관광지 보기"
            className="absolute right-[-14px] top-1/2 z-10 flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-full border border-[rgba(0,0,0,0.08)] bg-white text-[22px] leading-none text-text shadow-[0_6px_18px_rgba(0,0,0,0.08)] transition-transform hover:scale-105 max-[768px]:right-1"
          >
            ›
          </button>
        </>
      ) : null}
      <div
        ref={stripRef}
        id="placeStrip"
        className="kd-place-strip grid grid-flow-col auto-cols-[clamp(142px,13vw,164px)] gap-[clamp(12px,1.6vw,20px)] overflow-x-auto scroll-smooth pt-2 pb-2 pr-2 max-[768px]:auto-cols-[minmax(150px,72vw)]"
      >
        {places.map((place, idx) => {
          const isActive = idx === selectedPlaceIndex;
          const key = getPlaceSelectionKey(activeAlbum.id, place);
          const liked = likedPlaceKeys.has(key);
          return (
            <div
              key={`${place.name}-${idx}`}
              role="button"
              tabIndex={0}
              onClick={() => setSelectedPlaceIndex(idx)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  setSelectedPlaceIndex(idx);
                }
              }}
              className={`w-full min-w-0 h-[clamp(132px,15vh,148px)] rounded-[14px] bg-white relative cursor-pointer overflow-hidden transition-all border-2 ${
                isActive ? 'border-accent -translate-y-1' : 'border-[rgba(0,0,0,0.08)]'
              } hover:border-accent hover:-translate-y-1`}
            >
              <div className={`absolute top-2 left-2 z-[3] rounded-full bg-white/75 ${place.category === 'must' ? 'text-accent' : 'text-[#555]'} text-[9px] font-bold tracking-[0.08em] uppercase px-[7px] py-1 backdrop-blur-[10px]`}>
                {place.label}
              </div>
              <button
                type="button"
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  togglePlaceLike(activeAlbum.id, place.name, key, place);
                }}
                aria-pressed={liked}
                aria-label={`${place.name} ${liked ? '좋아요 취소' : '좋아요'}`}
                className={`absolute top-[7px] right-[7px] z-[4] w-7 h-7 rounded-full border border-white bg-white text-heart text-[16px] leading-none flex items-center justify-center cursor-pointer transition-all hover:scale-[1.08] ${liked ? 'border-white text-heart' : ''}`}
              >
                {liked ? '♥' : '♡'}
              </button>
              <div className="w-full h-full bg-white flex flex-col">
                {place.photo_url ? (
                  <div
                    className="h-[clamp(78px,9vh,92px)] shrink-0 bg-cover bg-center"
                    style={{ backgroundImage: `url("${place.photo_url}")` }}
                    aria-hidden="true"
                  />
                ) : (
                  <div className="h-[clamp(78px,9vh,92px)] shrink-0 flex items-center justify-center bg-accent-soft">
                    <span className="text-[30px]">{place.emoji || '🏛️'}</span>
                  </div>
                )}
                <div className="min-h-0 flex-1 flex flex-col justify-center gap-[3px] px-[10px]">
                  <p className="text-[10px] text-[#555] text-center leading-[1.35] line-clamp-2">{place.name}</p>
                  {place.source_keyword ? (
                    <span className="block text-[9px] text-accent text-center truncate">{place.source_keyword}</span>
                  ) : null}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
