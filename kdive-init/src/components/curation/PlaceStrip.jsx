'use client';

import { getPlaceKey } from '@/data/albums';
import { useKdive } from '@/store/KdiveContext';

export default function PlaceStrip({ places }) {
  const { activeAlbum, selectedPlaceIndex, setSelectedPlaceIndex, likedPlaceKeys, togglePlaceLike } = useKdive();

  if (!activeAlbum) return null;

  return (
    <div
      id="placeStrip"
      className="kd-place-strip grid gap-5 mb-[18px] w-[min(1160px,calc(100%-clamp(48px,6vw,96px)))] mx-auto max-[768px]:w-full max-[768px]:grid-flow-col max-[768px]:auto-cols-[minmax(140px,1fr)] max-[768px]:overflow-x-auto"
      style={{ gridTemplateColumns: 'repeat(5, minmax(0, 1fr))' }}
    >
      {places.map((place, idx) => {
        const isActive = idx === selectedPlaceIndex;
        const key = getPlaceKey(activeAlbum.id, place.name);
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
            className={`w-full min-w-0 h-[138px] rounded-[14px] bg-white relative cursor-pointer overflow-hidden transition-all border-2 ${
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
                togglePlaceLike(activeAlbum.id, place.name);
              }}
              aria-pressed={liked}
              aria-label={`${place.name} ${liked ? '좋아요 취소' : '좋아요'}`}
              className={`absolute top-[7px] right-[7px] z-[4] w-7 h-7 rounded-full border border-white bg-white text-heart text-[16px] leading-none flex items-center justify-center cursor-pointer transition-all hover:scale-[1.08] ${liked ? 'border-white text-heart' : ''}`}
            >
              {liked ? '♥' : '♡'}
            </button>
            <div className="w-full h-full flex flex-col items-center justify-center gap-[6px] bg-white pt-[26px] pb-3 px-[10px]">
              <span className="text-[28px]">{place.emoji}</span>
              <p className="text-[10px] text-[#555] text-center px-[6px]">{place.name}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
