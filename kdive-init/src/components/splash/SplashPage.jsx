'use client';

import { useEffect, useState } from 'react';
import { useKdive } from '@/store/KdiveContext';

/* ─────────────────────────────────────────────
   수면 반짝임 (고정값 — hydration 안전)
───────────────────────────────────────────── */
const SHIMMERS = [
  { top: '47%', left: '7%',  w: 3, h: 1.5, delay: '0.0s', dur: '2.1s' },
  { top: '50%', left: '15%', w: 2, h: 1.5, delay: '0.9s', dur: '1.7s' },
  { top: '46%', left: '24%', w: 4, h: 2,   delay: '0.3s', dur: '2.5s' },
  { top: '49%', left: '34%', w: 2, h: 1,   delay: '1.4s', dur: '1.9s' },
  { top: '48%', left: '46%', w: 3, h: 1.5, delay: '0.6s', dur: '2.3s' },
  { top: '51%', left: '57%', w: 2, h: 1,   delay: '1.1s', dur: '1.6s' },
  { top: '47%', left: '68%', w: 3, h: 1.5, delay: '0.2s', dur: '2.0s' },
  { top: '50%', left: '79%', w: 4, h: 2,   delay: '1.7s', dur: '2.4s' },
  { top: '46%', left: '89%', w: 2, h: 1,   delay: '0.5s', dur: '1.8s' },
];

/* ─────────────────────────────────────────────
   메인 컴포넌트
───────────────────────────────────────────── */
export default function SplashPage() {
  const { loggedIn } = useKdive();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setMounted(true), 100);
    return () => clearTimeout(t);
  }, []);

  if (loggedIn) return null;

  return (
    <>
      <style>{`
        @keyframes kd-fade-up {
          from { opacity: 0; transform: translateY(28px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        @keyframes kd-bounce-down {
          0%,100% { transform: translateX(-50%) translateY(0);   opacity: .55; }
          50%      { transform: translateX(-50%) translateY(9px); opacity: 1;   }
        }
        @keyframes kd-shimmer {
          0%,100% { opacity: 0; transform: scaleX(1);   }
          50%      { opacity: 1; transform: scaleX(1.4); }
        }
      `}</style>

      <section
        id="section-splash"
        style={{
          position: 'relative',
          width: '100%',
          overflow: 'hidden',
        }}
      >
        {/* ── 레이어 0: CSS 폴백 배경 (absolute로 영상 뒤를 채움) ── */}
        <div
          className="absolute inset-0"
          style={{
            background:
              'linear-gradient(180deg,#6EC6F0 0%,#4AAEDC 18%,#2090C8 34%,' +
              '#0A76AE 44%,#005A90 52%,#007EB5 62%,#00B8D8 78%,#70E4F0 92%,#C0F2FA 100%)',
            zIndex: 0,
          }}
        />

        {/* ── 레이어 1: 실사 비디오 — 16:9 원본 비율, 섹션 높이를 결정 ── */}
        <video
          autoPlay
          muted
          loop
          playsInline
          style={{
            display: 'block',
            width: '100%',
            aspectRatio: '16 / 9',
            objectFit: 'contain',
            position: 'relative',
            zIndex: 1,
          }}
        >
          <source src="/videos/ocean.mp4" type="video/mp4" />
        </video>

        {/* ── 레이어 2: 텍스트 가독성 오버레이 ── */}
        <div
          className="absolute inset-0"
          style={{
            background:
              'linear-gradient(108deg,rgba(0,18,65,0.52) 0%,rgba(0,18,65,0.26) 42%,transparent 70%)',
            zIndex: 2,
          }}
        />

        {/* ── 레이어 3: 하단 블렌딩 ── */}
        <div
          className="absolute bottom-0 left-0 right-0 pointer-events-none"
          style={{
            height: '28%',
            background: 'linear-gradient(to bottom,transparent,rgba(0,140,190,0.18))',
            zIndex: 3,
          }}
        />

        {/* ── 레이어 6: 수면 반짝임 ── */}
        {SHIMMERS.map((s, i) => (
          <div
            key={i}
            className="absolute pointer-events-none rounded-full"
            style={{
              top: s.top, left: s.left,
              width: s.w, height: s.h,
              background: 'rgba(255,255,255,0.95)',
              animation: `kd-shimmer ${s.dur} ease-in-out ${s.delay} infinite`,
              zIndex: 6,
            }}
          />
        ))}

        {/* ── 레이어 10: 텍스트 (absolute로 영상 위에 오버레이) ── */}
        <div
          className="absolute flex flex-col justify-center px-[clamp(32px,10vw,120px)]"
          style={{ top: 0, left: 0, right: 0, height: '55%', zIndex: 10 }}
        >
          <h1
            className="font-serif leading-none mb-5"
            style={{
              fontSize: 'clamp(3.8rem,9.5vw,8rem)',
              color: '#ffffff',
              textShadow: '0 2px 28px rgba(0,20,80,0.55),0 4px 64px rgba(0,10,50,0.3)',
              animation: mounted
                ? 'kd-fade-up 1.1s cubic-bezier(0.16,1,0.3,1) 0.2s both'
                : 'none',
              opacity: 0,
            }}
          >
            K-Dive
          </h1>

          {/* H3 — 16px */}
          <p
            className="font-mono mb-3"
            style={{
              fontSize: 16,
              color: 'rgba(255,255,255,0.95)',
              textShadow: '0 1px 12px rgba(0,20,80,0.5)',
              animation: mounted
                ? 'kd-fade-up 1.1s cubic-bezier(0.16,1,0.3,1) 0.75s both'
                : 'none',
              opacity: 0,
            }}
          >
            Your Playlist, Your Guide to an Extraordinary Journey Through Korea
          </p>

          {/* H4 — 12px */}
          <p
            style={{
              fontSize: 12,
              lineHeight: 1.85,
              color: 'rgba(255,255,255,0.82)',
              maxWidth: 560,
              textShadow: '0 1px 8px rgba(0,15,70,0.4)',
              animation: mounted
                ? 'kd-fade-up 1.1s cubic-bezier(0.16,1,0.3,1) 1.2s both'
                : 'none',
              opacity: 0,
            }}
          >
            Start with the K-Pop you love, and uncover Korea&apos;s culture, hidden gems,
            and local flavors tailored just for you.
            <br />
            Discover a Korea that is uniquely yours today.
            <br />
            <em style={{ fontStyle: 'italic', color: 'rgba(255,255,255,0.7)' }}>
              &ldquo;Tell us what you love. We&apos;ll gift you the Korea you&apos;re bound to fall in love with.&rdquo;
            </em>
          </p>

          <div
            className="mt-8 rounded-full"
            style={{
              width: 40, height: 3,
              background: 'rgba(255,255,255,0.6)',
              animation: mounted
                ? 'kd-fade-up 1.1s cubic-bezier(0.16,1,0.3,1) 1.6s both'
                : 'none',
              opacity: 0,
            }}
          />
        </div>

        {/* ── 스크롤 다운 인디케이터 ── */}
        <div
          className="absolute pointer-events-none"
          style={{
            bottom: 28, left: '50%', zIndex: 10,
            animation: 'kd-bounce-down 2.2s ease-in-out infinite',
          }}
        >
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
            <path
              d="M4 8L12 16L20 8"
              stroke="rgba(255,255,255,0.8)"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </div>
      </section>
    </>
  );
}
