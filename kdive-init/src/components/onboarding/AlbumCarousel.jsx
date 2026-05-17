'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ALBUMS, MIN_TRACK_SELECTION, VISIBLE_EDGE, VISIBLE_OFFSETS, normalizeAlbumIndex } from '@/data/albums';
import { useKdive } from '@/store/KdiveContext';
import AlbumCard from './AlbumCard';

function colorFromAlbumArt(src) {
  return new Promise((resolve) => {
    if (!src || typeof window === 'undefined') {
      resolve(null);
      return;
    }

    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.onload = () => {
      const canvas = document.createElement('canvas');
      const size = 24;
      canvas.width = size;
      canvas.height = size;
      const ctx = canvas.getContext('2d', { willReadFrequently: true });
      if (!ctx) {
        resolve(null);
        return;
      }
      ctx.drawImage(img, 0, 0, size, size);
      const { data } = ctx.getImageData(0, 0, size, size);
      let r = 0;
      let g = 0;
      let b = 0;
      let count = 0;

      for (let i = 0; i < data.length; i += 4) {
        const pr = data[i];
        const pg = data[i + 1];
        const pb = data[i + 2];
        const max = Math.max(pr, pg, pb);
        const min = Math.min(pr, pg, pb);
        const saturation = max - min;
        const brightness = (max + min) / 2;
        if (saturation < 22 || brightness < 28 || brightness > 232) continue;
        r += pr;
        g += pg;
        b += pb;
        count += 1;
      }

      if (!count) {
        resolve(null);
        return;
      }

      resolve(`rgb(${Math.round(r / count)}, ${Math.round(g / count)}, ${Math.round(b / count)})`);
    };
    img.onerror = () => resolve(null);
    img.src = src;
  });
}

// 원본의 getCarouselStyle을 그대로 옮긴 함수
function getCarouselStyle(offset, cardWidth) {
  const innerGap = cardWidth * 0.58;
  const middleGap = cardWidth * 0.44;
  const outerGap = cardWidth * 0.34;
  const positions = {
    1: innerGap,
    2: innerGap + middleGap,
    3: innerGap + middleGap + outerGap,
    4: innerGap + middleGap + outerGap + cardWidth * 0.28,
    5: innerGap + middleGap + outerGap + cardWidth * 0.50,
    6: innerGap + middleGap + outerGap + cardWidth * 0.68,
  };
  const sign = Math.sign(offset);
  const distance = Math.abs(offset);
  const overflowStep = Math.max(0, distance - 6);
  const tx = sign * (positions[distance] || positions[6] + cardWidth * 0.14 * overflowStep);
  const configs = {
    '-6': { tx, scale: 0.72, opacity: 1, zIndex: 0, filter: 'brightness(.16) saturate(.42)' },
    '-5': { tx, scale: 0.75, opacity: 1, zIndex: 0, filter: 'brightness(.20) saturate(.48)' },
    '-4': { tx, scale: 0.80, opacity: 1, zIndex: 1, filter: 'brightness(.28) saturate(.58)' },
    '-3': { tx, scale: 0.85, opacity: 1, zIndex: 2, filter: 'brightness(.38) saturate(.68)' },
    '-2': { tx, scale: 0.91, opacity: 1, zIndex: 3, filter: 'brightness(.54) saturate(.80)' },
    '-1': { tx, scale: 0.97, opacity: 1, zIndex: 4, filter: 'brightness(.74) saturate(.92)' },
    '0': { tx, scale: 1.04, opacity: 1, zIndex: 5, filter: 'brightness(1) saturate(1)' },
    '1': { tx, scale: 0.97, opacity: 1, zIndex: 4, filter: 'brightness(.74) saturate(.92)' },
    '2': { tx, scale: 0.91, opacity: 1, zIndex: 3, filter: 'brightness(.54) saturate(.80)' },
    '3': { tx, scale: 0.85, opacity: 1, zIndex: 2, filter: 'brightness(.38) saturate(.68)' },
    '4': { tx, scale: 0.80, opacity: 1, zIndex: 1, filter: 'brightness(.28) saturate(.58)' },
    '5': { tx, scale: 0.75, opacity: 1, zIndex: 0, filter: 'brightness(.20) saturate(.48)' },
    '6': { tx, scale: 0.72, opacity: 1, zIndex: 0, filter: 'brightness(.16) saturate(.42)' },
  };
  const key = String(offset);
  if (configs[key]) return configs[key];
  return null;
}

export default function AlbumCarousel() {
  const { currentIdx, goToIndex, likedTrackIds, toggleTrackLike } = useKdive();
  const stageRef = useRef(null);
  const [cardWidth, setCardWidth] = useState(220);
  const [vibeColor, setVibeColor] = useState('#00A8E8');
  const wheelLockRef = useRef(false);
  const dragStartXRef = useRef(0);
  const dragDeltaXRef = useRef(0);
  const suppressClickRef = useRef(false);
  const pointerCardIndexRef = useRef(null);
  const currentIdxRef = useRef(currentIdx);
  const carouselAnimatingRef = useRef(false);
  const sequenceTimerRef = useRef(null);
  const [cardMotion, setCardMotion] = useState({
    duration: 560,
    easing: 'cubic-bezier(0.22, 1, 0.36, 1)',
  });
  const currentAlbum = ALBUMS[currentIdx];
  const liked = currentAlbum ? likedTrackIds.has(currentAlbum.id) : false;
  const selectedTrackCount = likedTrackIds.size;

  useEffect(() => {
    currentIdxRef.current = currentIdx;
  }, [currentIdx]);

  useEffect(() => {
    let cancelled = false;
    colorFromAlbumArt(currentAlbum?.cover).then((color) => {
      if (!cancelled) setVibeColor(color || '#00A8E8');
    });
    return () => {
      cancelled = true;
    };
  }, [currentAlbum?.cover]);

  useEffect(() => {
    return () => {
      if (sequenceTimerRef.current) clearTimeout(sequenceTimerRef.current);
    };
  }, []);

  // 카드 크기 측정 (CSS clamp 결과를 JS에서 읽음)
  useEffect(() => {
    const stage = stageRef.current;
    if (!stage) return;
    const measure = () => {
      const rect = stage.getBoundingClientRect();
      const computed = Math.max(130, Math.min(340, rect.width * 0.18 - 20));
      setCardWidth(computed);
    };
    measure();
    window.addEventListener('resize', measure);
    return () => window.removeEventListener('resize', measure);
  }, []);

  const getSignedDiff = useCallback((targetIndex) => {
    let diff = normalizeAlbumIndex(targetIndex) - currentIdxRef.current;
    const half = Math.floor(ALBUMS.length / 2);
    if (diff > half) diff -= ALBUMS.length;
    if (diff < -half) diff += ALBUMS.length;
    return diff;
  }, []);

  const completeSequence = useCallback(() => {
    carouselAnimatingRef.current = false;
    suppressClickRef.current = false;
    setCardMotion({
      duration: 560,
      easing: 'cubic-bezier(0.22, 1, 0.36, 1)',
    });
  }, []);

  const activateRelativeStep = useCallback((step) => {
    if (carouselAnimatingRef.current) return;
    setCardMotion({
      duration: 560,
      easing: 'cubic-bezier(0.22, 1, 0.36, 1)',
    });
    goToIndex(currentIdxRef.current + step);
  }, [goToIndex]);

  const activateCard = useCallback((targetIndex) => {
    if (carouselAnimatingRef.current) return;
    const diff = getSignedDiff(targetIndex);
    if (!diff) return;

    const direction = Math.sign(diff);
    const totalSteps = Math.abs(diff);

    if (totalSteps > VISIBLE_EDGE) {
      setCardMotion({
        duration: 560,
        easing: 'cubic-bezier(0.22, 1, 0.36, 1)',
      });
      goToIndex(targetIndex);
      return;
    }

    if (totalSteps === 1) {
      activateRelativeStep(direction);
      return;
    }

    const quickEasing = 'cubic-bezier(0.22, 0.68, 0.34, 1)';
    const coastEasing = 'cubic-bezier(0.28, 0.74, 0.34, 1)';
    const settleEasing = 'cubic-bezier(0.16, 1, 0.3, 1)';
    carouselAnimatingRef.current = true;
    suppressClickRef.current = true;

    const runStep = (stepIndex) => {
      const isLast = stepIndex === totalSteps - 1;
      const duration = isLast ? (totalSteps >= 4 ? 320 : 330) : Math.min(170, 135 + stepIndex * 14);
      const easing = isLast ? settleEasing : (stepIndex === 0 ? quickEasing : coastEasing);

      setCardMotion({ duration, easing });
      goToIndex(currentIdxRef.current + direction);

      sequenceTimerRef.current = window.setTimeout(() => {
        if (isLast) {
          completeSequence();
          return;
        }
        runStep(stepIndex + 1);
      }, duration);
    };

    runStep(0);
  }, [activateRelativeStep, completeSequence, getSignedDiff, goToIndex]);

  // 휠 (스크롤) 입력
  useEffect(() => {
    const stage = stageRef.current;
    if (!stage) return;
    const onWheel = (event) => {
      event.preventDefault();
      if (wheelLockRef.current) return;
      const delta = Math.abs(event.deltaX) > Math.abs(event.deltaY) ? event.deltaX : event.deltaY;
      if (Math.abs(delta) < 8) return;
      wheelLockRef.current = true;
      if (delta > 0) activateRelativeStep(1);
      else activateRelativeStep(-1);
      setTimeout(() => {
        wheelLockRef.current = false;
      }, 420);
    };
    stage.addEventListener('wheel', onWheel, { passive: false });
    return () => stage.removeEventListener('wheel', onWheel);
  }, [activateRelativeStep]);

  const onPointerDown = useCallback((event) => {
    const card = event.target.closest?.('.kd-album-card');
    pointerCardIndexRef.current = card?.dataset?.index ? Number(card.dataset.index) : null;
    dragStartXRef.current = event.clientX;
    dragDeltaXRef.current = 0;
    stageRef.current?.classList.add('dragging');
    stageRef.current?.setPointerCapture(event.pointerId);
  }, []);

  const onPointerMove = useCallback((event) => {
    if (!stageRef.current?.classList.contains('dragging')) return;
    dragDeltaXRef.current = event.clientX - dragStartXRef.current;
  }, []);

  const onPointerUp = useCallback((event) => {
    stageRef.current?.classList.remove('dragging');
    if (stageRef.current?.hasPointerCapture(event.pointerId)) {
      stageRef.current.releasePointerCapture(event.pointerId);
    }
    if (Math.abs(dragDeltaXRef.current) > 42) {
      suppressClickRef.current = true;
      if (dragDeltaXRef.current < 0) activateRelativeStep(1);
      else activateRelativeStep(-1);
      setTimeout(() => {
        suppressClickRef.current = false;
      }, 120);
      pointerCardIndexRef.current = null;
      return;
    }

    const clickedIndex = pointerCardIndexRef.current;
    pointerCardIndexRef.current = null;
    if (Number.isInteger(clickedIndex) && clickedIndex !== currentIdx) {
      suppressClickRef.current = true;
      activateCard(clickedIndex);
      setTimeout(() => {
        suppressClickRef.current = false;
      }, 120);
    }
  }, [activateCard, activateRelativeStep, currentIdx]);

  // 카드 위치 계산 결과
  const cardConfigs = useMemo(() => {
    return VISIBLE_OFFSETS.map((offset) => {
      const albumIndex = normalizeAlbumIndex(currentIdx + offset);
      const style = getCarouselStyle(offset, cardWidth);
      return {
        offset,
        albumIndex,
        album: ALBUMS[albumIndex],
        style,
      };
    });
  }, [currentIdx, cardWidth]);

  const handleCardClick = useCallback((albumIndex) => {
    if (suppressClickRef.current) return;
    if (albumIndex === currentIdx) return; // 원본: 같은 카드는 togglePlay
    activateCard(albumIndex);
  }, [activateCard, currentIdx]);

  const handleSaveClick = useCallback(() => {
    if (!currentAlbum) return;
    toggleTrackLike(currentAlbum.id);
  }, [currentAlbum, toggleTrackLike]);

  return (
    <>
      <div
        ref={stageRef}
        className="relative w-full cursor-grab touch-pan-y"
        style={{
          '--card-w': `${cardWidth}px`,
          '--card-h': `${cardWidth * 1.1375}px`,
          '--kd-card-duration': `${cardMotion.duration}ms`,
          '--kd-card-easing': cardMotion.easing,
          height: `${cardWidth * 1.1375 - 2}px`,
        }}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
      >
        <div className="absolute inset-0 w-full h-full flex items-center justify-center overflow-hidden">
          {cardConfigs.map(({ offset, albumIndex, album, style }) => (
            <AlbumCard
              key={album.id}
              album={album}
              albumIndex={albumIndex}
              style={style}
              isFront={offset === 0}
              onClick={() => handleCardClick(albumIndex)}
              width={cardWidth}
            />
          ))}
        </div>
      </div>
      <div className="flex items-center justify-center gap-3 min-h-[34px]">
        <div
          className="max-w-[min(760px,calc(100%-32px))] min-w-0 flex items-center justify-center gap-3 rounded-full bg-white/88 px-4 py-[7px] shadow-[0_8px_24px_rgba(0,0,0,0.05)] backdrop-blur-[10px]"
          style={{ color: vibeColor }}
        >
          <span className="min-w-0 truncate text-[12px] font-bold tracking-[0.02em] max-[760px]:text-[12px]">
            {currentAlbum?.vibe || '–'}
          </span>
          {currentAlbum && (
            <button
              type="button"
              onClick={handleSaveClick}
              aria-label={`${currentAlbum.title} ${liked ? 'K-Dive 저장 취소' : 'K-Dive에 저장'}`}
              aria-pressed={liked}
              className="flex-shrink-0 border-0 bg-transparent p-0 text-[22px] leading-none transition-transform hover:scale-110"
              style={{ color: liked ? vibeColor : 'rgba(0,0,0,0.28)' }}
            >
              {liked ? '♥' : '♡'}
            </button>
          )}
        </div>
      </div>
      <p className="text-center text-[12px] text-muted min-h-[18px]">
        {selectedTrackCount < MIN_TRACK_SELECTION
          ? `${MIN_TRACK_SELECTION}곡 중 ${selectedTrackCount}곡 선택됨`
          : `${selectedTrackCount}곡 선택됨 · 관광지 추천을 준비했어요`}
      </p>
    </>
  );
}
