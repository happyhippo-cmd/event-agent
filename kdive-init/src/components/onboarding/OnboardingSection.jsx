'use client';

import { useEffect, useRef, useState } from 'react';
import { useKdive } from '@/store/KdiveContext';
import AlbumCarousel from './AlbumCarousel';
import PlayerBar from '@/components/player/PlayerBar';

export default function OnboardingSection() {
  const { appPhase, playerSlot } = useKdive();
  const sectionRef = useRef(null);
  const [popped, setPopped] = useState(false);

  // appPhase가 'onboarding'이 되면 스크롤 + 팝 애니메이션 발동
  useEffect(() => {
    if (appPhase !== 'onboarding') return;
    setPopped(false);
    document.getElementById('section-onboarding')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    const timer = setTimeout(() => setPopped(true), 80);
    return () => clearTimeout(timer);
  }, [appPhase]); // eslint-disable-line react-hooks/exhaustive-deps

  if (appPhase !== 'onboarding') return null;

  return (
    <section
      ref={sectionRef}
      id="section-onboarding"
      className="flex flex-col justify-start px-5 pt-[clamp(86px,10vh,112px)] pb-[clamp(24px,4vh,42px)] max-[760px]:px-4"
      style={{
        opacity: popped ? 1 : 0,
        transform: popped ? 'translateY(0) scale(1)' : 'translateY(44px) scale(0.96)',
        transition: 'opacity 0.65s cubic-bezier(0.34,1.56,0.64,1), transform 0.65s cubic-bezier(0.34,1.56,0.64,1)',
      }}
    >
      <div className="flex items-center gap-2 w-[min(1160px,calc(100%-clamp(48px,6vw,96px)))] mx-auto text-[12px] font-medium tracking-[0.14em] uppercase text-muted mb-3 max-[760px]:w-full">
        <span className="block w-6 h-px bg-accent" />
        Start with your vibe
      </div>
      <h1 className="font-serif w-[min(1160px,calc(100%-clamp(48px,6vw,96px)))] mx-auto text-[36px] leading-[1.08] mb-[8px] max-w-[1160px] max-[760px]:w-full max-[760px]:text-[34px]">
        Dive into Korea through <em className="italic text-accent">K-Pop</em>
      </h1>
      <p className="w-[min(1160px,calc(100%-clamp(48px,6vw,96px)))] mx-auto text-muted text-[16px] font-light leading-[1.55] max-w-[1160px] mb-[clamp(18px,3vh,28px)] max-[760px]:w-full max-[760px]:text-[15px]">
        Pick at least three tracks that match your mood.
        <br />
        We&apos;ll turn its rhythm into places, flavors, and moments to explore.
      </p>

      <div className="flex flex-col gap-[clamp(8px,1.2vh,12px)]">
        <AlbumCarousel />
        {playerSlot === 'onboarding' && (
          <div
            id="onboardingPlayerSlot"
            className="w-screen ml-[calc(50%-50vw)] mr-[calc(50%-50vw)] flex items-center justify-center min-h-[52px] sticky top-[61px] z-[80] bg-white/95 backdrop-blur-[12px] mt-[clamp(8px,1.6vh,16px)] py-3 px-[clamp(24px,6vw,72px)]"
          >
            <PlayerBar />
          </div>
        )}
      </div>
    </section>
  );
}
