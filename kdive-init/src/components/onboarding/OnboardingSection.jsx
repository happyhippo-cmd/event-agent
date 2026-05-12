'use client';

import { useKdive } from '@/store/KdiveContext';
import AlbumCarousel from './AlbumCarousel';
import PlayerBar from '@/components/player/PlayerBar';

export default function OnboardingSection() {
  const { loggedIn, playerSlot } = useKdive();
  if (loggedIn) return null;

  return (
    <section
      id="section-onboarding"
      className="flex flex-col justify-start px-5 pt-[clamp(86px,10vh,112px)] pb-[clamp(24px,4vh,42px)] max-[760px]:px-4"
    >
      <div className="flex items-center gap-2 w-[min(1160px,calc(100%-clamp(48px,6vw,96px)))] mx-auto text-[12px] font-medium tracking-[0.14em] uppercase text-muted mb-3 max-[760px]:w-full">
        <span className="block w-6 h-px bg-accent" />
        Start with your vibe
      </div>
      <h1 className="font-serif w-[min(1160px,calc(100%-clamp(48px,6vw,96px)))] mx-auto text-[36px] leading-[1.08] mb-[8px] max-w-[1160px] max-[760px]:w-full max-[760px]:text-[34px]">
        Dive into Korea through <em className="italic text-accent">K-Pop</em>
      </h1>
      <p className="w-[min(1160px,calc(100%-clamp(48px,6vw,96px)))] mx-auto text-muted text-[16px] font-light leading-[1.55] max-w-[1160px] mb-[clamp(18px,3vh,28px)] max-[760px]:w-full max-[760px]:text-[15px]">
        Pick a track that matches your mood.
        <br />
        We&apos;ll turn its rhythm into places, flavors, and moments to explore.
      </p>

      <div className="flex flex-col gap-[clamp(8px,1.2vh,12px)]">
        <AlbumCarousel />
        {/* 플레이어 바: 온보딩 슬롯에 위치할 때만 렌더 */}
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
