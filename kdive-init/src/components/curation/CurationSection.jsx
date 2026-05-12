'use client';

import { useMemo } from 'react';
import { getRecommendedPlaces } from '@/data/albums';
import { useKdive } from '@/store/KdiveContext';
import PlaceStrip from './PlaceStrip';
import PlaceDetail from './PlaceDetail';
import FoodSection from './FoodSection';
import PlayerBar from '@/components/player/PlayerBar';

export default function CurationSection() {
  const { activeAlbum, curationVisible, selectedPlaceIndex, playerSlot, loggedIn } = useKdive();
  const places = useMemo(() => getRecommendedPlaces(activeAlbum), [activeAlbum]);
  const selectedPlace = places[selectedPlaceIndex] || places[0];

  if (loggedIn || !curationVisible || !activeAlbum) return null;

  return (
    <section
      id="section-curation"
      className="block min-h-[auto] px-[clamp(24px,6vw,72px)] pt-4 pb-10 scroll-mt-[61px]"
    >
      {playerSlot === 'curation' && (
        <div className="curation-player-slot w-screen ml-[calc(50%-50vw)] mr-[calc(50%-50vw)] flex items-center justify-center min-h-[52px] sticky top-[61px] z-[80] bg-white/95 backdrop-blur-[12px] mb-[clamp(34px,3.6vh,46px)] py-[10px] px-[clamp(24px,6vw,72px)]">
          <PlayerBar />
        </div>
      )}
      <PlaceStrip places={places} />
      <div className="grid gap-5 w-[min(1160px,calc(100%-clamp(48px,6vw,96px)))] mx-auto max-[768px]:grid-cols-1 max-[768px]:w-full" style={{ gridTemplateColumns: 'minmax(0,1fr) minmax(0,1fr)' }}>
        <div className="min-w-0 rounded-[20px] overflow-hidden bg-surface border border-[rgba(0,0,0,0.08)] min-h-[380px] flex items-center justify-center">
          <div className="flex flex-col items-center gap-[10px] text-muted">
            <div className="text-[36px]">🗺️</div>
            <p className="text-[13px]">카카오맵 / 네이버맵 연동 예정</p>
          </div>
        </div>
        <PlaceDetail place={selectedPlace} album={activeAlbum} />
      </div>
      <FoodSection />
    </section>
  );
}
