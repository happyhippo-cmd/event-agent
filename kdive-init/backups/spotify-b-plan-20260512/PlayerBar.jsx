'use client';

import { useEffect } from 'react';
import { ALBUMS } from '@/data/albums';
import { useKdive } from '@/store/KdiveContext';
import Waveform from './Waveform';

export default function PlayerBar() {
  const {
    activeAlbum, currentIdx,
    isPlaying, setIsPlaying,
    setWaveformProgress,
    nextCard, prevCard,
  } = useKdive();

  const album = activeAlbum || ALBUMS[currentIdx];

  // 곡 바뀌면 진행도 리셋
  useEffect(() => {
    setWaveformProgress(0);
    setIsPlaying(false);
  }, [album?.id, setIsPlaying, setWaveformProgress]);

  const togglePlay = () => {
    setIsPlaying((p) => !p);
  };

  const handlePrev = () => {
    const resume = isPlaying;
    prevCard();
    if (resume) {
      // 다음 곡으로 자연스럽게 이어 재생 — 원본 동작 모사
      setIsPlaying(true);
    }
  };

  const handleNext = () => {
    const resume = isPlaying;
    nextCard();
    if (resume) {
      setIsPlaying(true);
    }
  };

  return (
    <div
      id="sharedPlayerBar"
      className="grid items-center justify-center w-[min(1160px,calc(100%-clamp(48px,6vw,96px)))] p-0 gap-x-[18px] gap-y-[18px] max-[760px]:w-full max-[760px]:gap-2"
      style={{
        gridTemplateColumns: 'minmax(0,1fr) auto',
        gridTemplateAreas: '"meta vibe" "wave controls"',
      }}
    >
      <div className="min-w-0 flex items-baseline gap-[14px] max-[760px]:gap-2" style={{ gridArea: 'meta' }}>
        <div className="font-serif text-[clamp(1.25rem,1.75vw,1.62rem)] leading-[1.05] whitespace-nowrap overflow-hidden text-ellipsis max-[760px]:text-[1.25rem]">
          {album?.title || '–'}
        </div>
        <div className="text-[16px] font-medium text-muted whitespace-nowrap overflow-hidden text-ellipsis max-[760px]:text-[13px]">
          {album?.artist || '–'}
        </div>
      </div>
      <div className="flex-shrink-0 flex items-center gap-[6px]" style={{ gridArea: 'controls' }}>
        <button
          type="button"
          onClick={handlePrev}
          aria-label="이전 곡"
          className="w-[30px] h-[30px] rounded-full border border-[rgba(0,0,0,0.08)] bg-white text-text text-[11px] cursor-pointer flex items-center justify-center transition-all shadow-[0_2px_8px_rgba(0,0,0,0.06)] hover:border-accent hover:text-accent hover:scale-[1.06]"
        >
          ⏮
        </button>
        <button
          type="button"
          onClick={togglePlay}
          aria-label="재생 또는 일시정지"
          className="flex-shrink-0 w-[30px] h-[30px] rounded-full border-0 bg-accent text-white text-[12px] cursor-pointer flex items-center justify-center transition-all shadow-[0_3px_10px_rgba(0,168,232,0.34)] hover:bg-accent-dark hover:scale-[1.08] active:scale-[0.95]"
        >
          {isPlaying ? '⏸' : '▶'}
        </button>
        <button
          type="button"
          onClick={handleNext}
          aria-label="다음 곡"
          className="w-[30px] h-[30px] rounded-full border border-[rgba(0,0,0,0.08)] bg-white text-text text-[11px] cursor-pointer flex items-center justify-center transition-all shadow-[0_2px_8px_rgba(0,0,0,0.06)] hover:border-accent hover:text-accent hover:scale-[1.06]"
        >
          ⏭
        </button>
      </div>
      <Waveform seed={currentIdx} />
      <div
        className="text-[14px] tracking-[0.02em] text-accent text-right whitespace-nowrap overflow-hidden text-ellipsis max-[760px]:text-left max-[760px]:text-[12px]"
        style={{ gridArea: 'vibe' }}
      >
        {album?.vibe || '–'}
      </div>
    </div>
  );
}
