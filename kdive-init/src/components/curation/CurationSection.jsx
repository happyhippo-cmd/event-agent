'use client';

import { useEffect, useMemo } from 'react';
import { MIN_TRACK_SELECTION, getRecommendedPlaces } from '@/data/albums';
import { useKdive } from '@/store/KdiveContext';
import PlaceStrip from './PlaceStrip';
import PlaceDetail from './PlaceDetail';
import FoodSection from './FoodSection';
import PlayerBar from '@/components/player/PlayerBar';

export default function CurationSection() {
  const {
    activeAlbum,
    likedTrackIds,
    onboardingPlaces,
    placesLoading,
    placesError,
    retryOnboardingPlaces,
    curationVisible,
    selectedPlaceIndex,
    setSelectedPlaceIndex,
    playerSlot,
    loggedIn,
  } = useKdive();
  const fallbackPlaces = useMemo(() => getRecommendedPlaces(activeAlbum), [activeAlbum]);
  const shouldUseAgentPlaces = likedTrackIds.size >= MIN_TRACK_SELECTION;
  const places = shouldUseAgentPlaces && onboardingPlaces.length ? onboardingPlaces : fallbackPlaces;
  const selectedPlace = places[selectedPlaceIndex] || places[0];

  useEffect(() => {
    if (selectedPlaceIndex >= places.length) setSelectedPlaceIndex(0);
  }, [places.length, selectedPlaceIndex, setSelectedPlaceIndex]);

  if (loggedIn || !curationVisible || !activeAlbum) return null;

  return (
    <section
      id="section-curation"
      className="block min-h-[calc(100vh-61px)] px-[clamp(24px,6vw,72px)] pt-[clamp(10px,1.6vh,16px)] pb-[clamp(18px,2.4vh,28px)] scroll-mt-[61px]"
    >
      {playerSlot === 'curation' && (
        <div className="curation-player-slot w-screen ml-[calc(50%-50vw)] mr-[calc(50%-50vw)] flex items-center justify-center min-h-[52px] sticky top-[61px] z-[80] bg-white/95 backdrop-blur-[12px] mb-[clamp(14px,2vh,22px)] py-2 px-[clamp(24px,6vw,72px)]">
          <PlayerBar />
        </div>
      )}
      {placesLoading ? (
        <div className="w-[min(1160px,calc(100%-clamp(48px,6vw,96px)))] mx-auto mb-3 rounded-[14px] border border-accent-border bg-accent-soft px-5 py-3 text-[13px] text-accent-dark">
          Tour Agent가 선택한 노래 키워드와 어울리는 관광지를 고르고 있어요.
        </div>
      ) : null}
      {placesError ? (
        <div className="w-[min(1160px,calc(100%-clamp(48px,6vw,96px)))] mx-auto mb-3 rounded-[14px] border border-[rgba(0,0,0,0.08)] bg-white px-5 py-3 text-[13px] text-muted flex items-center justify-between gap-4 max-[640px]:items-start max-[640px]:flex-col">
          <span>{placesError}</span>
          <button
            type="button"
            onClick={retryOnboardingPlaces}
            className="shrink-0 h-8 rounded-full border border-accent-border bg-accent-soft px-4 text-[12px] font-bold text-accent-dark transition-colors hover:bg-white"
          >
            다시 시도
          </button>
        </div>
      ) : null}
      <PlaceStrip places={places} />
      <div className="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)] items-stretch gap-[clamp(14px,2vw,20px)] w-[min(1160px,calc(100%-clamp(48px,6vw,96px)))] mx-auto max-[768px]:grid-cols-1 max-[768px]:w-full">
        <div className="min-w-0 h-[clamp(260px,34vh,360px)] rounded-[20px] overflow-hidden bg-surface border border-[rgba(0,0,0,0.08)] flex items-center justify-center max-[768px]:h-[300px]">
          {selectedPlace?.photo_url ? (
            <div
              className="w-full h-full bg-cover bg-center"
              style={{ backgroundImage: `url("${selectedPlace.photo_url}")` }}
              aria-label={`${selectedPlace.name} 사진`}
            />
          ) : (
            <div className="flex flex-col items-center gap-[10px] text-muted">
              <div className="text-[36px]">{selectedPlace?.emoji || '🗺️'}</div>
              <p className="text-[13px]">장소 사진 준비 중</p>
            </div>
          )}
        </div>
        <PlaceDetail place={selectedPlace} album={activeAlbum} places={places} />
      </div>
      <FoodSection places={places} />
    </section>
  );
}
