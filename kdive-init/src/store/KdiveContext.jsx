'use client';

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { ALBUMS, MIN_TRACK_SELECTION, getPlaceKey } from '@/data/albums';
import { deleteHistoryItem, postHistoryItem } from '@/utils/historyApi';
import {
  buildFoodPayload,
  buildPlacePayload,
  buildRestorePayloadFromHistoryItem,
  buildTrackPayload,
} from '@/utils/historyPayload';
import { getSurfyApiUrl } from '@/utils/surfyApi';

const LIKED_STORAGE_KEY = 'kdive-liked-tracks';
const LEGACY_LIKED_STORAGE_KEY = 'kdive-liked-albums';
const LIKED_PLACES_STORAGE_KEY = 'kdive-liked-places';
const LIKED_FOODS_STORAGE_KEY = 'kdive-liked-foods';
const VISITED_HISTORY_STORAGE_KEY = 'kdive-visited-history';
const PENDING_UNLIKE_STORAGE_KEY = 'kdive-pending-unlike';

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
  const [visitedHistoryKeys, setVisitedHistoryKeys] = useState(() => new Set());
  const [visitedHistoryRecords, setVisitedHistoryRecords] = useState(() => ({}));
  // History에서 하트를 다시 눌러 7일 유예 제거를 예약한 아이템 키 집합.
  // 실제 like 상태(likedTrackIds/likedPlaceKeys/likedFoodKeys)는 유지하되,
  // History 카드의 liked 표시와 백엔드 DELETE만 이 집합으로 분리 관리한다.
  const [pendingUnlikeKeys, setPendingUnlikeKeys] = useState(() => new Set());
  const [onboardingPlaces, setOnboardingPlaces] = useState([]);
  const [placesLoading, setPlacesLoading] = useState(false);
  const [placesError, setPlacesError] = useState('');
  const [placesRetryToken, setPlacesRetryToken] = useState(0);
  // 섹션 표시
  const [curationVisible, setCurationVisible] = useState(false);
  const [foodVisible, setFoodVisible] = useState(false);
  const [authVisible, setAuthVisible] = useState(false);
  const [authInitialTab, setAuthInitialTab] = useState('login');
  const [guestMode, setGuestMode] = useState(false);
  // 'onboarding': 온보딩 화면 | 'app': 로그인 후 메인 앱 화면
  const [appPhase, setAppPhase] = useState(null);
  // 현재 로그인된 유저 정보
  const [currentUser, setCurrentUser] = useState(null);
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
    try {
      const stored = JSON.parse(localStorage.getItem(VISITED_HISTORY_STORAGE_KEY) || '[]');
      const keys = Array.isArray(stored)
        ? stored.map((item) => (typeof item === 'string' ? item : item?.key)).filter(Boolean)
        : [];
      setVisitedHistoryKeys(new Set(keys));
      const records = {};
      if (Array.isArray(stored)) {
        stored.forEach((item) => {
          if (item?.key && item?.record) records[item.key] = item.record;
        });
      }
      setVisitedHistoryRecords(records);
    } catch (e) {}
    try {
      const stored = JSON.parse(localStorage.getItem(PENDING_UNLIKE_STORAGE_KEY) || '[]');
      if (Array.isArray(stored)) {
        setPendingUnlikeKeys(new Set(stored.filter((k) => typeof k === 'string')));
      }
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
  }, [likedTrackIds, placesRetryToken]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    try {
      localStorage.setItem(LIKED_PLACES_STORAGE_KEY, JSON.stringify(Array.from(likedPlaceKeys).map((key) => ({
        key,
        place: likedPlaceRecords[key],
      }))));
    } catch (e) {}
  }, [likedPlaceKeys, likedPlaceRecords]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    try {
      localStorage.setItem(LIKED_FOODS_STORAGE_KEY, JSON.stringify(Array.from(likedFoodKeys).map((key) => ({
        key,
        food: likedFoodRecords[key],
      }))));
    } catch (e) {}
  }, [likedFoodKeys, likedFoodRecords]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    try {
      localStorage.setItem(VISITED_HISTORY_STORAGE_KEY, JSON.stringify(Array.from(visitedHistoryKeys).map((key) => ({
        key,
        record: visitedHistoryRecords[key],
      }))));
    } catch (e) {}
  }, [visitedHistoryKeys, visitedHistoryRecords]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    try {
      localStorage.setItem(PENDING_UNLIKE_STORAGE_KEY, JSON.stringify(Array.from(pendingUnlikeKeys)));
    } catch (e) {}
  }, [pendingUnlikeKeys]);

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
    const itemKey = `track-${albumId}`;
    if (alreadyLiked) {
      void deleteHistoryItem(itemKey).catch(() => {});
    } else if (album) {
      void postHistoryItem(buildTrackPayload(album, { source: 'onboarding' })).catch(() => {});
    }

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
    const itemKey = `place-${key}`;

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

    if (shouldUnlike) {
      void deleteHistoryItem(itemKey).catch(() => {});
      return;
    }

    void postHistoryItem(
      buildPlacePayload({ itemKey, albumId, placeName, placeRecord })
    ).catch(() => {});
  }, [likedPlaceKeys]);

  const toggleFoodLike = useCallback((foodKey, foodRecord) => {
    const shouldUnlike = likedFoodKeys.has(foodKey);
    const itemKey = `food-${foodKey}`;

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

    if (shouldUnlike) {
      void deleteHistoryItem(itemKey).catch(() => {});
      return;
    }

    void postHistoryItem(
      buildFoodPayload({ itemKey, foodKey, foodRecord })
    ).catch(() => {});
  }, [likedFoodKeys]);

  const toggleHistoryVisit = useCallback((historyKey, historyRecord) => {
    const shouldUnvisit = visitedHistoryKeys.has(historyKey);
    setVisitedHistoryKeys((prev) => {
      const next = new Set(prev);
      if (next.has(historyKey)) next.delete(historyKey);
      else next.add(historyKey);
      return next;
    });
    setVisitedHistoryRecords((records) => {
      const nextRecords = { ...records };
      if (shouldUnvisit) delete nextRecords[historyKey];
      else if (historyRecord) nextRecords[historyKey] = historyRecord;
      return nextRecords;
    });

    if (shouldUnvisit) {
      void deleteHistoryItem(historyRecord?.place_key || historyKey).catch(() => {});
      return;
    }

    void postHistoryItem({
      item_key: historyRecord?.item_key || historyKey,
      item_type: historyRecord?.type === 'food' ? 'restaurant' : 'attraction',
      title: historyRecord?.title || historyKey,
      category: historyRecord?.label || historyRecord?.type || 'place',
      place_key: historyRecord?.place_key || historyKey,
      visited_source: 'history',
      payload: historyRecord || {},
    }).catch(() => {});
  }, [visitedHistoryKeys]);

  // History 카드의 하트를 눌렀을 때 호출.
  // 이미 예약 중이면 예약을 취소(=복구 POST), 아니면 예약(=DELETE).
  // 실제 like 상태는 그대로 두고 pendingUnlikeKeys 만 토글한다.
  const togglePendingUnlike = useCallback((historyItem) => {
    if (!historyItem?.key) return;
    const itemKey = historyItem.key;
    const isScheduled = pendingUnlikeKeys.has(itemKey);

    setPendingUnlikeKeys((prev) => {
      const next = new Set(prev);
      if (next.has(itemKey)) next.delete(itemKey);
      else next.add(itemKey);
      return next;
    });

    if (isScheduled) {
      void postHistoryItem(buildRestorePayloadFromHistoryItem(historyItem)).catch(() => {});
      return;
    }
    void deleteHistoryItem(itemKey).catch(() => {});
  }, [pendingUnlikeKeys]);

  const showAuth = useCallback((tab = 'login') => {
    setAuthInitialTab(tab);
    setAuthVisible(true);
    scrollToSection('authSection');
  }, [scrollToSection]);

  const goGuest = useCallback(() => {
    setGuestMode(true);
    setAppPhase('onboarding');
  }, []);
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
    setAppPhase('onboarding');
    scrollToSection('section-onboarding');
  }, [scrollToSection]);

  // 비회원 → 로그인/회원가입 전환 (guestMode 해제 후 authSection 표시)
  const convertGuestToAuth = useCallback((tab = 'login') => {
    setGuestMode(false);
    setAuthInitialTab(tab);
    setAuthVisible(true);
    scrollToSection('authSection');
  }, [scrollToSection]);

  const loginToSurfy = useCallback((user = null) => {
    setLoggedIn(true);
    setCurrentUser(user);
    setAuthVisible(false);
    setCurationVisible(false);
    setFoodVisible(false);
    setPlayerSlot('onboarding');
    setAppPhase('onboarding'); // 로그인 후 온보딩 먼저
  }, []);

  const showAppPage = useCallback((page) => {
    setActiveAppPage(page);
    setAppPhase('app'); // 온보딩 → 앱으로 전환
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
    visitedHistoryKeys, visitedHistoryRecords,
    pendingUnlikeKeys,
    onboardingPlaces, placesLoading, placesError,
    curationVisible, foodVisible, authVisible, authInitialTab, guestMode, appPhase, loggedIn, currentUser, activeAppPage,
    selectedPlaceIndex, setSelectedPlaceIndex,
    isPlaying, setIsPlaying,
    waveformProgress, setWaveformProgress,
    playerSlot, setPlayerSlot,
    goToIndex, nextCard, prevCard,
    toggleTrackLike, togglePlaceLike, toggleFoodLike, toggleHistoryVisit, togglePendingUnlike,
    showAuth, hideAuth, showFood, hideFood, goGuest,
    retryOnboardingPlaces, showCurationForAlbum, goBackToOnboarding, loginToSurfy, showAppPage, convertGuestToAuth,
  }), [
    currentIdx, activeAlbum, activeAlbumId,
    likedTrackIds, likedPlaceKeys, likedPlaceRecords, likedFoodKeys, likedFoodRecords,
    visitedHistoryKeys, visitedHistoryRecords,
    pendingUnlikeKeys,
    onboardingPlaces, placesLoading, placesError,
    curationVisible, foodVisible, authVisible, authInitialTab, guestMode, appPhase, loggedIn, currentUser, activeAppPage,
    selectedPlaceIndex,
    isPlaying, waveformProgress, playerSlot,
    goToIndex, nextCard, prevCard,
    toggleTrackLike, togglePlaceLike, toggleFoodLike, toggleHistoryVisit, togglePendingUnlike,
    showAuth, hideAuth, showFood, hideFood, goGuest,
    retryOnboardingPlaces, showCurationForAlbum, goBackToOnboarding, loginToSurfy, showAppPage, convertGuestToAuth,
  ]);

  return <KdiveContext.Provider value={value}>{children}</KdiveContext.Provider>;
}

export function useKdive() {
  const ctx = useContext(KdiveContext);
  if (!ctx) throw new Error('useKdive must be used inside KdiveProvider');
  return ctx;
}
