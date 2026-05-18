'use client';

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { ALBUMS, MIN_TRACK_SELECTION, getPlaceKey } from '@/data/albums';
import { getSurfyApiUrl } from '@/utils/surfyApi';

const LIKED_STORAGE_KEY = 'kdive-liked-tracks';
const LEGACY_LIKED_STORAGE_KEY = 'kdive-liked-albums';
const LIKED_PLACES_STORAGE_KEY = 'kdive-liked-places';
const LIKED_FOODS_STORAGE_KEY = 'kdive-liked-foods';
const SHOULD_PERSIST_SELECTIONS = process.env.NODE_ENV === 'production';

const KdiveContext = createContext(null);

export function KdiveProvider({ children }) {
  // 캐러셀 / 활성 앨범
  const [currentIdx, setCurrentIdx] = useState(0);
  const [activeAlbumId, setActiveAlbumId] = useState(ALBUMS[0]?.id);
  // 좋아요
  const [likedTrackIds, setLikedTrackIds] = useState(() => new Set());
  const [likedPlaceKeys, setLikedPlaceKeys] = useState(() => new Set());
  const [likedPlaceRecords, setLikedPlaceRecords] = useState(() => ({}));
  const [likedFoodKeys, setLikedFoodKeys] = useState(() => new Set());
  const [likedFoodRecords, setLikedFoodRecords] = useState(() => ({}));
  const [onboardingPlaces, setOnboardingPlaces] = useState([]);
  const [placesLoading, setPlacesLoading] = useState(false);
  const [placesError, setPlacesError] = useState('');
  const [placesRetryToken, setPlacesRetryToken] = useState(0);
  // 섹션 표시
  const [curationVisible, setCurationVisible] = useState(false);
  const [foodVisible, setFoodVisible] = useState(false);
  const [authVisible, setAuthVisible] = useState(false);
  const [loggedIn, setLoggedIn] = useState(false);
  const [activeAppPage, setActiveAppPage] = useState('surfy');
  // 큐레이션 내부 상태
  const [selectedPlaceIndex, setSelectedPlaceIndex] = useState(0);
  // 플레이어 상태
  const [isPlaying, setIsPlaying] = useState(false);
  const [waveformProgress, setWaveformProgress] = useState(0);
  // 플레이어 바 부모 슬롯 (onboarding | curation)
  const [playerSlot, setPlayerSlot] = useState('onboarding');

  // localStorage hydration
  useEffect(() => {
    if (typeof window === 'undefined') return;
    if (!SHOULD_PERSIST_SELECTIONS) {
      localStorage.removeItem(LIKED_STORAGE_KEY);
      localStorage.removeItem(LEGACY_LIKED_STORAGE_KEY);
      localStorage.removeItem(LIKED_PLACES_STORAGE_KEY);
      localStorage.removeItem(LIKED_FOODS_STORAGE_KEY);
      return;
    }
    try {
      const rawTracks = localStorage.getItem(LIKED_STORAGE_KEY) || localStorage.getItem(LEGACY_LIKED_STORAGE_KEY) || '[]';
      const storedTracks = JSON.parse(rawTracks);
      const items = Array.isArray(storedTracks) ? storedTracks : [];
      const ids = items.map((item) => (typeof item === 'string' ? item : item?.id)).filter(Boolean);
      const keywords = items.map((item) => (typeof item === 'string' ? null : item?.keyword || item?.vibe)).filter(Boolean);
      const validIds = ids.filter((id) => ALBUMS.some((a) => a.id === id));
      const idsFromKeywords = ALBUMS.filter((album) => keywords.includes(album.vibe)).map((album) => album.id);
      const nextIds = [...validIds, ...idsFromKeywords];
      if (nextIds.length) setLikedTrackIds(new Set(nextIds));
    } catch (e) {
      // ignore
    }
    try {
      const stored = JSON.parse(localStorage.getItem(LIKED_PLACES_STORAGE_KEY) || '[]');
      const keys = Array.isArray(stored)
        ? stored.map((item) => (typeof item === 'string' ? item : item?.key)).filter(Boolean)
        : [];
      setLikedPlaceKeys(new Set(keys));
      const records = {};
      if (Array.isArray(stored)) {
        stored.forEach((item) => {
          if (item?.key && item?.place) records[item.key] = item.place;
        });
      }
      setLikedPlaceRecords(records);
    } catch (e) {}
    try {
      const stored = JSON.parse(localStorage.getItem(LIKED_FOODS_STORAGE_KEY) || '[]');
      const keys = Array.isArray(stored)
        ? stored.map((item) => (typeof item === 'string' ? item : item?.key)).filter(Boolean)
        : [];
      setLikedFoodKeys(new Set(keys));
      const records = {};
      if (Array.isArray(stored)) {
        stored.forEach((item) => {
          if (item?.key && item?.food) records[item.key] = item.food;
        });
      }
      setLikedFoodRecords(records);
    } catch (e) {}
  }, []);

  // 좋아요 영속화
  useEffect(() => {
    if (typeof window === 'undefined') return;
    if (!SHOULD_PERSIST_SELECTIONS) return;
    const list = ALBUMS.filter((a) => likedTrackIds.has(a.id)).map((a) => ({
      keyword: a.vibe,
    }));
    try {
      localStorage.setItem(LIKED_STORAGE_KEY, JSON.stringify(list));
      localStorage.removeItem(LEGACY_LIKED_STORAGE_KEY);
    } catch (e) {}
  }, [likedTrackIds, placesRetryToken]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    if (!SHOULD_PERSIST_SELECTIONS) return;
    try {
      localStorage.setItem(LIKED_PLACES_STORAGE_KEY, JSON.stringify(Array.from(likedPlaceKeys).map((key) => ({
        key,
        place: likedPlaceRecords[key],
      }))));
    } catch (e) {}
  }, [likedPlaceKeys, likedPlaceRecords]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    if (!SHOULD_PERSIST_SELECTIONS) return;
    try {
      localStorage.setItem(LIKED_FOODS_STORAGE_KEY, JSON.stringify(Array.from(likedFoodKeys).map((key) => ({
        key,
        food: likedFoodRecords[key],
      }))));
    } catch (e) {}
  }, [likedFoodKeys, likedFoodRecords]);

  useEffect(() => {
    if (likedTrackIds.size < MIN_TRACK_SELECTION) {
      setOnboardingPlaces([]);
      setPlacesLoading(false);
      setPlacesError('');
      return undefined;
    }

    const controller = new AbortController();
    const tracks = ALBUMS.filter((album) => likedTrackIds.has(album.id)).map((album) => ({
      id: album.id,
      title: album.title,
      artist: album.artist,
      vibe: album.vibe,
      seed_places: album.places,
    }));

    setPlacesLoading(true);
    setPlacesError('');
    fetch(getSurfyApiUrl('/api/onboarding/places/'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tracks, fixed_count: 2, per_keyword: 3 }),
      signal: controller.signal,
    })
      .then((response) => response.json().then((data) => ({ response, data })).catch(() => ({ response, data: {} })))
      .then(({ response, data }) => {
        if (!response.ok) throw new Error(data?.detail || data?.message || 'places_request_failed');
        setOnboardingPlaces(Array.isArray(data?.places) ? data.places : []);
        setSelectedPlaceIndex(0);
      })
      .catch((error) => {
        if (error.name === 'AbortError') return;
        setPlacesError('관광지 추천을 불러오지 못했어요. 잠시 후 다시 시도해 주세요.');
        setOnboardingPlaces([]);
      })
      .finally(() => {
        if (!controller.signal.aborted) setPlacesLoading(false);
      });

    return () => controller.abort();
  }, [likedTrackIds]);

  const scrollToSection = useCallback((sectionId, options = {}) => {
    if (typeof window === 'undefined') return;
    window.requestAnimationFrame(() => {
      window.requestAnimationFrame(() => {
        const section = document.getElementById(sectionId);
        if (!section) return;

        if (!options.belowPlayer) {
          section.scrollIntoView({
            behavior: 'smooth',
            block: 'start',
          });
          return;
        }

        const navHeight = document.querySelector('nav')?.getBoundingClientRect().height || 61;
        const playerHeight = document.querySelector('.curation-player-slot')?.getBoundingClientRect().height || 150;
        const targetTop = Math.max(
          0,
          window.scrollY + section.getBoundingClientRect().top - navHeight - playerHeight - 12
        );

        window.scrollTo({
          top: targetTop,
          behavior: 'smooth',
        });
      });
    });
  }, []);

  // 액션
  const goToIndex = useCallback((idx) => {
    const normalized = ((idx % ALBUMS.length) + ALBUMS.length) % ALBUMS.length;
    setCurrentIdx(normalized);
    setActiveAlbumId(ALBUMS[normalized].id);
  }, []);

  const nextCard = useCallback(() => goToIndex(currentIdx + 1), [currentIdx, goToIndex]);
  const prevCard = useCallback(() => goToIndex(currentIdx - 1), [currentIdx, goToIndex]);

  const toggleTrackLike = useCallback((albumId) => {
    const next = new Set(likedTrackIds);
    const alreadyLiked = next.has(albumId);
    if (alreadyLiked) next.delete(albumId);
    else next.add(albumId);
    setLikedTrackIds(next);

    const album = ALBUMS.find((a) => a.id === albumId);
    if (album) {
      const idx = ALBUMS.findIndex((a) => a.id === albumId);
      if (idx >= 0) {
        setCurrentIdx(idx);
        setActiveAlbumId(albumId);
      }
    }

    if (next.size >= MIN_TRACK_SELECTION) {
      setCurationVisible(true);
      setFoodVisible(false);
      setSelectedPlaceIndex(0);
      setPlayerSlot('curation');
      scrollToSection('section-curation');
      return;
    }

    setCurationVisible(false);
    setFoodVisible(false);
    setPlayerSlot('onboarding');
  }, [likedTrackIds, scrollToSection]);

  const togglePlaceLike = useCallback((albumId, placeName, explicitKey, placeRecord) => {
    const key = explicitKey || getPlaceKey(albumId, placeName);
    const shouldUnlike = likedPlaceKeys.has(key);
    setLikedPlaceKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
    setLikedPlaceRecords((records) => {
      const nextRecords = { ...records };
      if (shouldUnlike) delete nextRecords[key];
      else if (placeRecord) nextRecords[key] = placeRecord;
      return nextRecords;
    });
  }, [likedPlaceKeys]);

  const toggleFoodLike = useCallback((foodKey, foodRecord) => {
    const shouldUnlike = likedFoodKeys.has(foodKey);
    setLikedFoodKeys((prev) => {
      const next = new Set(prev);
      if (next.has(foodKey)) next.delete(foodKey);
      else next.add(foodKey);
      return next;
    });
    setLikedFoodRecords((records) => {
      const nextRecords = { ...records };
      if (shouldUnlike) delete nextRecords[foodKey];
      else if (foodRecord) nextRecords[foodKey] = foodRecord;
      return nextRecords;
    });
  }, [likedFoodKeys]);

  const showAuth = useCallback(() => {
    setAuthVisible(true);
    scrollToSection('authSection');
  }, [scrollToSection]);
  const hideAuth = useCallback(() => setAuthVisible(false), []);
  const showFood = useCallback(() => {
    setFoodVisible(true);
    setPlayerSlot('curation');
    scrollToSection('foodSection', { belowPlayer: true });
  }, [scrollToSection]);
  const hideFood = useCallback(() => {
    setFoodVisible(false);
  }, []);
  const retryOnboardingPlaces = useCallback(() => {
    setPlacesRetryToken((value) => value + 1);
  }, []);
  const showCurationForAlbum = useCallback((album) => {
    if (!album) return;
    const idx = ALBUMS.findIndex((a) => a.id === album.id);
    if (idx >= 0) {
      setCurrentIdx(idx);
      setActiveAlbumId(album.id);
    }
    setCurationVisible(true);
    setSelectedPlaceIndex(0);
    setPlayerSlot('curation');
    setFoodVisible(false);
    if (likedTrackIds.size >= MIN_TRACK_SELECTION && placesError) {
      setPlacesRetryToken((value) => value + 1);
    }
    scrollToSection('section-curation');
  }, [likedTrackIds.size, placesError, scrollToSection]);
  const goBackToOnboarding = useCallback(() => {
    setCurationVisible(false);
    setFoodVisible(false);
    setAuthVisible(false);
    setPlayerSlot('onboarding');
    scrollToSection('section-onboarding');
  }, [scrollToSection]);

  const loginToSurfy = useCallback(() => {
    setLoggedIn(true);
    setActiveAppPage('surfy');
    setCurationVisible(false);
    setAuthVisible(false);
    setFoodVisible(false);
    setPlayerSlot('onboarding');
    if (typeof window !== 'undefined') {
      window.requestAnimationFrame(() => {
        window.scrollTo({ top: 0, behavior: 'auto' });
      });
    }
  }, []);

  const showAppPage = useCallback((page) => {
    setActiveAppPage(page);
    if (typeof window !== 'undefined') {
      window.requestAnimationFrame(() => {
        window.scrollTo({ top: 0, behavior: 'auto' });
      });
    }
  }, []);

  const activeAlbum = useMemo(() => ALBUMS.find((a) => a.id === activeAlbumId) || ALBUMS[currentIdx], [activeAlbumId, currentIdx]);

  const value = useMemo(() => ({
    currentIdx, activeAlbum, activeAlbumId,
    likedTrackIds, likedPlaceKeys, likedPlaceRecords, likedFoodKeys, likedFoodRecords,
    onboardingPlaces, placesLoading, placesError,
    curationVisible, foodVisible, authVisible, loggedIn, activeAppPage,
    selectedPlaceIndex, setSelectedPlaceIndex,
    isPlaying, setIsPlaying,
    waveformProgress, setWaveformProgress,
    playerSlot, setPlayerSlot,
    goToIndex, nextCard, prevCard,
    toggleTrackLike, togglePlaceLike, toggleFoodLike,
    showAuth, hideAuth, showFood, hideFood,
    retryOnboardingPlaces, showCurationForAlbum, goBackToOnboarding, loginToSurfy, showAppPage,
  }), [
    currentIdx, activeAlbum, activeAlbumId,
    likedTrackIds, likedPlaceKeys, likedPlaceRecords, likedFoodKeys, likedFoodRecords,
    onboardingPlaces, placesLoading, placesError,
    curationVisible, foodVisible, authVisible, loggedIn, activeAppPage,
    selectedPlaceIndex,
    isPlaying, waveformProgress, playerSlot,
    goToIndex, nextCard, prevCard,
    toggleTrackLike, togglePlaceLike, toggleFoodLike,
    showAuth, hideAuth, showFood, hideFood,
    retryOnboardingPlaces, showCurationForAlbum, goBackToOnboarding, loginToSurfy, showAppPage,
  ]);

  return <KdiveContext.Provider value={value}>{children}</KdiveContext.Provider>;
}

export function useKdive() {
  const ctx = useContext(KdiveContext);
  if (!ctx) throw new Error('useKdive must be used inside KdiveProvider');
  return ctx;
}
