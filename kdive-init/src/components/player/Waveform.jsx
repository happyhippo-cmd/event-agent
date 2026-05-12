'use client';

import { useEffect, useMemo, useRef } from 'react';
import { PLAYBACK_DURATION_MS } from '@/data/albums';
import { useKdive } from '@/store/KdiveContext';

const BAR_COUNT = 128;

function buildBars(seed) {
  return Array.from({ length: BAR_COUNT }, (_, i) => {
    const x = i / Math.max(1, BAR_COUNT - 1);
    const waveA = Math.abs(Math.sin((i + 1 + seed * 11) * 0.42));
    const waveB = Math.abs(Math.sin((i + 1 + seed * 7) * 0.17));
    const beatPulse = Math.pow(Math.max(0, Math.sin((x * (10 + (seed % 5)) + seed * 0.11) * Math.PI)), 5);
    const chorusLift =
      Math.exp(-Math.pow((x - 0.28 - ((seed % 3) * 0.035)) / 0.11, 2)) * 0.38 +
      Math.exp(-Math.pow((x - 0.62 + ((seed % 4) * 0.02)) / 0.15, 2)) * 0.34;
    const energy = Math.min(1, 0.16 + waveA * 0.22 + waveB * 0.18 + beatPulse * 0.3 + chorusLift);
    const height = Math.round(3 + energy * 24);
    return {
      index: i,
      height,
      energy,
      beat: beatPulse,
      phase: i * 0.36 + seed * 0.77,
    };
  });
}

export default function Waveform({ seed = 0 }) {
  const containerRef = useRef(null);
  const animationRef = useRef(null);
  const lastFrameRef = useRef(0);
  const { isPlaying, waveformProgress, setWaveformProgress } = useKdive();

  const bars = useMemo(() => buildBars(seed), [seed]);

  // 재생 진행 애니메이션
  useEffect(() => {
    if (!isPlaying) {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
        animationRef.current = null;
        lastFrameRef.current = 0;
      }
      return;
    }
    const tick = (timestamp) => {
      if (!lastFrameRef.current) lastFrameRef.current = timestamp;
      const delta = timestamp - lastFrameRef.current;
      lastFrameRef.current = timestamp;
      setWaveformProgress((prev) => {
        const next = Math.min(1, (prev || 0) + delta / PLAYBACK_DURATION_MS);
        return next;
      });
      animationRef.current = requestAnimationFrame(tick);
    };
    animationRef.current = requestAnimationFrame(tick);
    return () => {
      if (animationRef.current) cancelAnimationFrame(animationRef.current);
      animationRef.current = null;
      lastFrameRef.current = 0;
    };
  }, [isPlaying, setWaveformProgress]);

  // progress가 1에 도달하면 자동 정지
  useEffect(() => {
    if (waveformProgress >= 1 && isPlaying) {
      // 플레이어 측에서 처리하도록 isPlaying만 false로
    }
  }, [waveformProgress, isPlaying]);

  const handleSeek = (event) => {
    const bounds = event.currentTarget.getBoundingClientRect();
    const progress = Math.max(0, Math.min(1, (event.clientX - bounds.left) / bounds.width));
    setWaveformProgress(progress);
  };

  const activeIndex = waveformProgress * Math.max(1, BAR_COUNT - 1);

  return (
    <div
      ref={containerRef}
      id="waveform"
      onClick={handleSeek}
      className="w-full h-[30px] min-w-[120px] cursor-pointer flex items-center justify-between overflow-hidden px-[3px]"
      style={{ gridArea: 'wave' }}
    >
      {bars.map((bar) => {
        const distance = Math.abs(bar.index - activeIndex);
        const isActive = bar.index <= activeIndex;
        const isCurrent = distance <= 2;
        return (
          <span
            key={bar.index}
            className={`kd-wave-bar ${isActive ? 'active' : ''} ${isPlaying ? 'playing' : ''} ${isCurrent ? 'current' : ''}`}
            style={{ height: `${bar.height}px` }}
          />
        );
      })}
    </div>
  );
}
