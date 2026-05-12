'use client';

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { ALBUMS, getPlaceKey } from '@/data/albums';

const LIKED_STORAGE_KEY = 'kdive-liked-tracks';
const LEGACY_LIKED_STORAGE_KEY = 'kdive-liked-albums';
const LIKED_PLACES_STORAGE_KEY = 'kdive-liked-places';
const LIKED_FOODS_STORAGE_KEY = 'kdive-liked-foods';

const KdiveContext = createContext(null);

export function KdiveProvider({ children }) {
  // 캐러셀 / 활성 앨범
  const [currentIdx, setCurrentIdx] = useState(0);
  const [activeAlbumId, setActiveAlbumId] = useState(ALBUMS[0]?.id);
  // 좋아요
  const [likedTrackIds, setLikedTrackIds] = useState(() => new Set());
  const [likedPlaceKeys, setLikedPlaceKeys] = useState(() => new Set());
  const [likedFoodKeys, setLikedFoodKeys] = useState(() => new Set());
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
    } catch (e) {}
    try {
      const stored = JSON.parse(localStorage.getItem(LIKED_FOODS_STORAGE_KEY) || '[]');
      const keys = Array.isArray(stored)
        ? stored.map((item) => (typeof item === 'string' ? item : item?.key)).filter(Boolean)
        : [];
      setLikedFoodKeys(new Set(keys));
    } catch (e) {}
  }, []);

  // 좋아요 영속화
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const list = ALBUMS.filter((a) => likedTrackIds.has(a.id)).map((a) => ({
      keyword: a.vibe,
    }));
    try {
      localStorage.setItem(LIKED_STORAGE_KEY, JSON.stringify(list));
      localStorage.removeItem(LEGACY_LIKED_STORAGE_KEY);
    } catch (e) {}
  }, [likedTrackIds]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    try {
      localStorage.setItem(LIKED_PLACES_STORAGE_KEY, JSON.stringify(Array.from(likedPlaceKeys).map((key) => ({ key }))));
    } catch (e) {}
  }, [likedPlaceKeys]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    try {
      localStorage.setItem(LIKED_FOODS_STORAGE_KEY, JSON.stringify(Array.from(likedFoodKeys).map((key) => ({ key }))));
    } catch (e) {}
  }, [likedFoodKeys]);

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
    const alreadyLiked = likedTrackIds.has(albumId);
    setLikedTrackIds((prev) => {
      const next = new Set(prev);
      if (next.has(albumId)) next.delete(albumId);
      else next.add(albumId);
      return next;
    });
    // 원본: 좋아요 시 큐레이션 자동 표시
    const album = ALBUMS.find((a) => a.id === albumId);
    if (album && !alreadyLiked) {
      const idx = ALBUMS.findIndex((a) => a.id === albumId);
      if (idx >= 0) {
        setCurrentIdx(idx);
        setActiveAlbumId(albumId);
      }
      setCurationVisible(true);
      setFoodVisible(false);
      setSelectedPlaceIndex(0);
      setPlayerSlot('curation');
      scrollToSection('section-curation');
    }
  }, [likedTrackIds, scrollToSection]);

  const togglePlaceLike = useCallback((albumId, placeName) => {
    const key = getPlaceKey(albumId, placeName);
    setLikedPlaceKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }, []);

  const toggleFoodLike = useCallback((foodKey) => {
    setLikedFoodKeys((prev) => {
      const next = new Set(prev);
      if (next.has(foodKey)) next.delete(foodKey);
      else next.add(foodKey);
      return next;
    });
  }, []);

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
    scrollToSection('section-curation');
  }, [scrollToSection]);
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
    likedTrackIds, likedPlaceKeys, likedFoodKeys,
    curationVisible, foodVisible, authVisible, loggedIn, activeAppPage,
    selectedPlaceIndex, setSelectedPlaceIndex,
    isPlaying, setIsPlaying,
    waveformProgress, setWaveformProgress,
    playerSlot, setPlayerSlot,
    goToIndex, nextCard, prevCard,
    toggleTrackLike, togglePlaceLike, toggleFoodLike,
    showAuth, hideAuth, showFood, hideFood,
    showCurationForAlbum, goBackToOnboarding, loginToSurfy, showAppPage,
  }), [
    currentIdx, activeAlbum, activeAlbumId,
    likedTrackIds, likedPlaceKeys, likedFoodKeys,
    curationVisible, foodVisible, authVisible, loggedIn, activeAppPage,
    selectedPlaceIndex,
    isPlaying, waveformProgress, playerSlot,
    goToIndex, nextCard, prevCard,
    toggleTrackLike, togglePlaceLike, toggleFoodLike,
    showAuth, hideAuth, showFood, hideFood,
    showCurationForAlbum, goBackToOnboarding, loginToSurfy, showAppPage,
  ]);

  return <KdiveContext.Provider value={value}>{children}</KdiveContext.Provider>;
}

export function useKdive() {
  const ctx = useContext(KdiveContext);
  if (!ctx) throw new Error('useKdive must be used inside KdiveProvider');
  return ctx;
}
