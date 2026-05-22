'use client';

import { useEffect, useState } from 'react';
import { useKdive } from '@/store/KdiveContext';

export default function SplashPage() {
  const { loggedIn } = useKdive();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setMounted(true), 80);
    return () => clearTimeout(t);
  }, []);

  if (loggedIn) return null;

  const handleScrollDown = () => {
    const target = document.getElementById('section-onboarding');
    if (target) target.scrollIntoView({ behavior: 'smooth' });
  };

  return (
    <>
      <style>{`
        @keyframes kd-wave-slow {
          from { transform: translateX(0); }
          to   { transform: translateX(-50%); }
        }
        @keyframes kd-wave-mid {
          from { transform: translateX(-8%); }
          to   { transform: translateX(-58%); }
        }
        @keyframes kd-wave-fast {
          from { transform: translateX(-4%); }
          to   { transform: translateX(-54%); }
        }
        @keyframes kd-fade-up {
          from { opacity: 0; transform: translateY(22px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        @keyframes kd-arrow-bob {
          0%, 100% { transform: translateX(-50%) translateY(0px); opacity: 0.45; }
          50%       { transform: translateX(-50%) translateY(9px); opacity: 0.75; }
        }
        @keyframes kd-particle-drift {
          0%   { transform: translateY(0) translateX(0) scale(1); opacity: 0.5; }
          50%  { transform: translateY(-18px) translateX(8px) scale(1.1); opacity: 0.8; }
          100% { transform: translateY(0) translateX(0) scale(1); opacity: 0.5; }
        }
      `}</style>

      <section
        id="section-splash"
        className="relative w-full overflow-hidden flex flex-col justify-center"
        style={{ height: '100svh', background: 'linear-gradient(175deg, #eaf8ff 0%, #f4fbff 40%, #ffffff 100%)' }}
      >
        {/* 배경 빛 번짐 */}
        <div
          className="absolute pointer-events-none"
          style={{
            top: '8%',
            right: '12%',
            width: 'clamp(260px,30vw,440px)',
            height: 'clamp(260px,30vw,440px)',
            background: 'radial-gradient(circle, rgba(0,168,232,0.12) 0%, transparent 70%)',
            borderRadius: '50%',
          }}
        />
        <div
          className="absolute pointer-events-none"
          style={{
            bottom: '38%',
            left: '6%',
            width: 'clamp(160px,18vw,280px)',
            height: 'clamp(160px,18vw,280px)',
            background: 'radial-gradient(circle, rgba(0,168,232,0.08) 0%, transparent 70%)',
            borderRadius: '50%',
          }}
        />

        {/* 부유 파티클 */}
        {[
          { top: '22%', left: '18%', size: 6, delay: '0s', dur: '4.2s' },
          { top: '35%', left: '72%', size: 4, delay: '1.1s', dur: '5.5s' },
          { top: '55%', left: '88%', size: 5, delay: '0.6s', dur: '3.8s' },
          { top: '18%', left: '55%', size: 3, delay: '2s',   dur: '6s'   },
          { top: '70%', left: '25%', size: 4, delay: '0.3s', dur: '4.8s' },
        ].map((p, i) => (
          <div
            key={i}
            className="absolute pointer-events-none rounded-full"
            style={{
              top: p.top,
              left: p.left,
              width: p.size,
              height: p.size,
              background: 'rgba(0,168,232,0.5)',
              animation: `kd-particle-drift ${p.dur} ease-in-out ${p.delay} infinite`,
            }}
          />
        ))}

        {/* ── 파도 레이어 ── */}
        <div
          className="absolute bottom-0 left-0 right-0 pointer-events-none select-none"
          style={{ height: '42%' }}
        >
          {/* 파도 3 — 뒤 (가장 느림) */}
          <svg
            className="absolute bottom-0 left-0"
            style={{
              width: '200%',
              height: '100%',
              animation: 'kd-wave-slow 18s linear infinite',
            }}
            viewBox="0 0 2880 200"
            preserveAspectRatio="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              d="M0,130 C360,70 1080,190 1440,130 C1800,70 2520,190 2880,130 L2880,200 L0,200 Z"
              fill="rgba(0,168,232,0.09)"
            />
          </svg>

          {/* 파도 2 — 중간 */}
          <svg
            className="absolute bottom-0 left-0"
            style={{
              width: '200%',
              height: '100%',
              animation: 'kd-wave-mid 11s linear infinite',
            }}
            viewBox="0 0 2880 200"
            preserveAspectRatio="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              d="M0,110 C360,50 1080,170 1440,110 C1800,50 2520,170 2880,110 L2880,200 L0,200 Z"
              fill="rgba(0,168,232,0.17)"
            />
          </svg>

          {/* 파도 1 — 앞 (가장 빠름) */}
          <svg
            className="absolute bottom-0 left-0"
            style={{
              width: '200%',
              height: '100%',
              animation: 'kd-wave-fast 7s linear infinite',
            }}
            viewBox="0 0 2880 200"
            preserveAspectRatio="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              d="M0,88 C360,34 1080,142 1440,88 C1800,34 2520,142 2880,88 L2880,200 L0,200 Z"
              fill="rgba(0,168,232,0.28)"
            />
          </svg>

          {/* 파도 최전면 — 얕은 거품 */}
          <svg
            className="absolute bottom-0 left-0"
            style={{
              width: '200%',
              height: '100%',
              animation: 'kd-wave-fast 5s linear infinite reverse',
            }}
            viewBox="0 0 2880 200"
            preserveAspectRatio="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              d="M0,160 C360,140 1080,180 1440,160 C1800,140 2520,180 2880,160 L2880,200 L0,200 Z"
              fill="rgba(0,168,232,0.13)"
            />
          </svg>
        </div>

        {/* ── 메인 콘텐츠 ── */}
        <div className="relative z-10 px-[clamp(32px,10vw,120px)]">
          {/* K-Dive 타이틀 */}
          <h1
            className="font-serif text-text leading-none mb-5"
            style={{
              fontSize: 'clamp(3.8rem,9.5vw,8rem)',
              animation: mounted ? 'kd-fade-up 1s cubic-bezier(0.22,1,0.36,1) 0.15s both' : 'none',
              opacity: mounted ? undefined : 0,
            }}
          >
            K-Dive
          </h1>

          {/* 태그라인 */}
          <p
            className="text-text font-mono mb-3"
            style={{
              fontSize: 'clamp(0.95rem,1.8vw,1.2rem)',
              animation: mounted ? 'kd-fade-up 1s cubic-bezier(0.22,1,0.36,1) 0.65s both' : 'none',
              opacity: mounted ? undefined : 0,
            }}
          >
            Start with your vibe,
          </p>

          {/* 설명 */}
          <p
            className="text-muted leading-relaxed max-w-[500px]"
            style={{
              fontSize: 'clamp(0.82rem,1.1vw,0.95rem)',
              lineHeight: 1.85,
              animation: mounted ? 'kd-fade-up 1s cubic-bezier(0.22,1,0.36,1) 1.05s both' : 'none',
              opacity: mounted ? undefined : 0,
            }}
          >
            K-Pop 음악에서 시작해 한국의 문화, 명소, 음식을 발견하는
            <br />
            새로운 방식의 한국 여행 큐레이션 플랫폼
          </p>

          {/* 액센트 바 */}
          <div
            className="mt-8 rounded-full"
            style={{
              width: 40,
              height: 3,
              background: 'rgba(0,168,232,0.55)',
              animation: mounted ? 'kd-fade-up 1s cubic-bezier(0.22,1,0.36,1) 1.35s both' : 'none',
              opacity: mounted ? undefined : 0,
            }}
          />
        </div>

        {/* ── 스크롤 다운 화살표 ── */}
        <button
          type="button"
          onClick={handleScrollDown}
          aria-label="아래로 스크롤"
          className="absolute border-0 bg-transparent cursor-pointer p-2"
          style={{
            bottom: 28,
            left: '50%',
            animation: 'kd-arrow-bob 2.2s ease-in-out infinite',
          }}
        >
          <svg
            width="22"
            height="22"
            viewBox="0 0 22 22"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              d="M4 7.5L11 15L18 7.5"
              stroke="rgba(0,0,0,0.28)"
              strokeWidth="1.6"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
      </section>
    </>
  );
}
