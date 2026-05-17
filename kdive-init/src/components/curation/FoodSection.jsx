'use client';

import { useEffect, useMemo, useState } from 'react';
import {
  FOOD_RESULT_LIMIT,
  MIN_PLACE_SELECTION,
  createFoodSuggestionsForPlace,
  getPlaceSelectionKey,
  getRecommendedPlaces,
} from '@/data/albums';
import { useKdive } from '@/store/KdiveContext';
import { getSurfyApiUrl } from '@/utils/surfyApi';

export default function FoodSection({ places = [] }) {
  const { activeAlbum, foodVisible, likedPlaceKeys, likedFoodKeys, toggleFoodLike, showAuth } = useKdive();
  const [activeFoodKey, setActiveFoodKey] = useState(null);
  const [agentFoods, setAgentFoods] = useState([]);
  const [foodsLoading, setFoodsLoading] = useState(false);
  const [foodsError, setFoodsError] = useState('');

  const sourcePlaces = useMemo(() => {
    if (!activeAlbum) return [];
    const candidates = places.length ? places : getRecommendedPlaces(activeAlbum);
    return candidates.filter((p) => likedPlaceKeys.has(getPlaceSelectionKey(activeAlbum.id, p)));
  }, [activeAlbum, likedPlaceKeys, places]);

  useEffect(() => {
    if (!foodVisible || sourcePlaces.length < MIN_PLACE_SELECTION) {
      setAgentFoods([]);
      setFoodsLoading(false);
      setFoodsError('');
      return undefined;
    }

    const controller = new AbortController();
    setFoodsLoading(true);
    setFoodsError('');
    fetch(getSurfyApiUrl('/api/onboarding/foods/'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ places: sourcePlaces, limit: FOOD_RESULT_LIMIT, radius_km: 2.0 }),
      signal: controller.signal,
    })
      .then((response) => response.json().then((data) => ({ response, data })).catch(() => ({ response, data: {} })))
      .then(({ response, data }) => {
        if (!response.ok) throw new Error(data?.detail || data?.message || 'foods_request_failed');
        setAgentFoods(Array.isArray(data?.foods) ? data.foods : []);
      })
      .catch((error) => {
        if (error.name === 'AbortError') return;
        setFoodsError('근처 맛집을 불러오지 못했어요. 잠시 후 다시 시도해 주세요.');
        setAgentFoods([]);
      })
      .finally(() => {
        if (!controller.signal.aborted) setFoodsLoading(false);
      });

    return () => controller.abort();
  }, [foodVisible, sourcePlaces]);

  useEffect(() => {
    if (!foodVisible) return undefined;

    let frameId = 0;
    const timerId = window.setTimeout(() => {
      frameId = window.requestAnimationFrame(() => {
        const section = document.getElementById('foodSection');
        if (!section) return;

        const navHeight = document.querySelector('nav')?.getBoundingClientRect().height || 61;
        const playerHeight = document.getElementById('sharedPlayerBar')?.getBoundingClientRect().height
          || document.querySelector('.curation-player-slot')?.getBoundingClientRect().height
          || 140;
        const targetTop = Math.max(
          0,
          window.scrollY + section.getBoundingClientRect().top - navHeight - playerHeight - 18
        );

        window.scrollTo({ top: targetTop, behavior: 'smooth' });
      });
    }, 40);

    return () => {
      window.clearTimeout(timerId);
      if (frameId) window.cancelAnimationFrame(frameId);
    };
  }, [foodVisible]);

  const suggestions = useMemo(() => {
    if (agentFoods.length) return agentFoods;
    if (places.some((place) => place.source_agent === 'tourist')) return [];
    if (!activeAlbum || !sourcePlaces.length) return [];
    const perPlace = sourcePlaces.map((place) => createFoodSuggestionsForPlace(activeAlbum, place));
    const mixed = [];
    for (let typeIndex = 0; mixed.length < FOOD_RESULT_LIMIT; typeIndex += 1) {
      let added = false;
      perPlace.forEach((arr) => {
        if (mixed.length < FOOD_RESULT_LIMIT && arr[typeIndex]) {
          mixed.push(arr[typeIndex]);
          added = true;
        }
      });
      if (!added) break;
    }
    return mixed;
  }, [activeAlbum, agentFoods, places, sourcePlaces]);

  if (!foodVisible || !activeAlbum) return null;

  return (
    <section
      id="foodSection"
      className="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)] items-stretch gap-[clamp(14px,2vw,20px)] mt-[clamp(18px,2.6vh,28px)] w-[min(1160px,calc(100%-clamp(48px,6vw,96px)))] mx-auto scroll-mt-[220px] max-[768px]:w-full max-[768px]:grid-cols-1"
      aria-hidden="false"
    >
      <div className="min-w-0 h-[clamp(300px,calc(100vh-260px),500px)] rounded-[20px] overflow-hidden bg-white border border-[rgba(0,0,0,0.08)] flex items-center justify-center max-[768px]:h-[320px]">
        <div className="flex flex-col items-center gap-[10px] text-muted">
          <div className="text-[36px]">🍜</div>
          <p className="text-[13px]">근처 맛집 지도</p>
        </div>
      </div>
      <div className="kd-food-list min-w-0 h-[clamp(300px,calc(100vh-260px),500px)] flex flex-col gap-3 overflow-y-auto py-1 pr-2 max-[768px]:h-auto max-[768px]:max-h-[420px]">
        {foodsLoading ? (
          <div className="rounded-[14px] border border-accent-border bg-accent-soft px-5 py-4 text-[13px] text-accent-dark">
            Foodie Agent가 선택한 관광지 근처 맛집을 장르가 겹치지 않게 고르고 있어요.
          </div>
        ) : null}
        {foodsError ? (
          <div className="rounded-[14px] border border-[rgba(0,0,0,0.08)] bg-white px-5 py-4 text-[13px] text-muted">
            {foodsError}
          </div>
        ) : null}
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
                className="w-full min-h-[72px] border-0 bg-transparent font-pretendard pl-[18px] pr-[58px] py-[13px] flex flex-col justify-center gap-1 text-left cursor-pointer"
              >
                <span className="text-[11px] text-accent font-semibold">
                  {[item.placeName, item.genre || item.type, item.distance_km ? `${item.distance_km}km` : null].filter(Boolean).join(' · ')}
                </span>
                <strong className="text-[14px] font-bold text-text">{item.title || item.name}</strong>
                <span className="text-[12px] text-black/55 font-normal leading-[1.45]">{item.desc}</span>
              </div>
              <div className="kd-food-card-detail">
                <div className="min-h-[104px] overflow-hidden pb-[2px] flex flex-col justify-center">
                  <div className="text-[10px] tracking-[0.1em] uppercase text-accent mb-[6px]">
                    {item.placeName} Foodie curation
                  </div>
                  <p className="text-[12px] text-black/60 leading-[1.6]">{item.curation}</p>
                </div>
              </div>
            </article>
          );
        })}
        {!foodsLoading && !suggestions.length ? (
          <div className="rounded-[14px] border border-[rgba(0,0,0,0.08)] bg-white px-5 py-4 text-[13px] text-muted">
            {sourcePlaces.length >= MIN_PLACE_SELECTION
              ? '조건에 맞는 근처 맛집을 찾지 못했어요.'
              : '관광지를 3곳 이상 선택하면 근처 맛집 5곳을 추천할게요.'}
          </div>
        ) : null}
        <button
          type="button"
          onClick={showAuth}
          className="w-full min-h-[46px] border border-[rgba(0,0,0,0.08)] rounded-[14px] bg-white text-text font-pretendard text-[13px] font-semibold cursor-pointer transition-all hover:shadow-[0_4px_14px_rgba(0,0,0,0.04)]"
        >
          더 많은 장소를 탐색하고 싶다면?
        </button>
      </div>
    </section>
  );
}
