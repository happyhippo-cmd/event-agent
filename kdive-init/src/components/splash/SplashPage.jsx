'use client';

import { useEffect, useRef, useState } from 'react';
import { useKdive } from '@/store/KdiveContext';

/* ── 거품 파티클 (Canvas) ──────────────────── */
function useFoamCanvas(canvasRef) {
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    const resize = () => {
      canvas.width  = canvas.offsetWidth;
      canvas.height = canvas.offsetHeight;
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(canvas);

    // 거품 정의
    const BUBBLE_COUNT = 110;
    const makeParticle = (w, h) => ({
      x:       Math.random() * w,
      y:       h * 0.55 + Math.random() * h * 0.45,
      r:       0.8 + Math.random() * 3.5,
      opacity: 0.25 + Math.random() * 0.55,
      vx:      (Math.random() - 0.5) * 0.6,
      vy:      -0.15 - Math.random() * 0.7,
      life:    0,
      maxLife: 70 + Math.random() * 140,
    });

    const particles = Array.from({ length: BUBBLE_COUNT }, () => {
      const p = makeParticle(canvas.width, canvas.height);
      p.life = Math.random() * p.maxLife; // 초기 위상 분산
      return p;
    });

    let rafId;
    const tick = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      const w = canvas.width;
      const h = canvas.height;

      particles.forEach((p, i) => {
        p.life++;
        if (p.life >= p.maxLife) { particles[i] = makeParticle(w, h); return; }
        p.x += p.vx;
        p.y += p.vy;
        const ratio = p.life / p.maxLife;
        const alpha = p.opacity * Math.sin(ratio * Math.PI); // fade in & out
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(255,255,255,${alpha})`;
        ctx.fill();
      });

      rafId = requestAnimationFrame(tick);
    };
    tick();

    return () => { cancelAnimationFrame(rafId); ro.disconnect(); };
  }, [canvasRef]);
}

/* ── 수면 반짝임 위치 (고정값 — hydration 안전) ── */
const SHIMMERS = [
  { top: '47%', left: '6%',  w: 3, h: 1.5, delay: '0.0s', dur: '2.1s' },
  { top: '50%', left: '14%', w: 2, h: 1.5, delay: '0.9s', dur: '1.7s' },
  { top: '46%', left: '22%', w: 4, h: 2,   delay: '0.3s', dur: '2.5s' },
  { top: '49%', left: '31%', w: 2, h: 1,   delay: '1.4s', dur: '1.9s' },
  { top: '47%', left: '42%', w: 3, h: 1.5, delay: '0.6s', dur: '2.3s' },
  { top: '51%', left: '53%', w: 2, h: 1,   delay: '1.1s', dur: '1.6s' },
  { top: '48%', left: '63%', w: 3, h: 1.5, delay: '0.2s', dur: '2.0s' },
  { top: '50%', left: '73%', w: 4, h: 2,   delay: '1.7s', dur: '2.4s' },
  { top: '46%', left: '83%', w: 2, h: 1,   delay: '0.5s', dur: '1.8s' },
  { top: '49%', left: '92%', w: 3, h: 1.5, delay: '1.2s', dur: '2.2s' },
];

/* ── 메인 컴포넌트 ───────────────────────── */
export default function SplashPage() {
  const { loggedIn } = useKdive();
  const [mounted, setMounted] = useState(false);
  const canvasRef = useRef(null);

  useFoamCanvas(canvasRef);

  useEffect(() => {
    const t = setTimeout(() => setMounted(true), 80);
    return () => clearTimeout(t);
  }, []);

  if (loggedIn) return null;

  const scrollDown = () =>
    document.getElementById('section-onboarding')?.scrollIntoView({ behavior: 'smooth' });

  return (
    <>
      <style>{`
        @keyframes kd-wave-a { from{transform:translateX(0)} to{transform:translateX(-50%)} }
        @keyframes kd-wave-b { from{transform:translateX(-12%)} to{transform:translateX(-62%)} }
        @keyframes kd-wave-c { from{transform:translateX(-5%)} to{transform:translateX(-55%)} }
        @keyframes kd-wave-d { from{transform:translateX(-22%)} to{transform:translateX(-72%)} }
        @keyframes kd-fade-up {
          from { opacity:0; transform:translateY(22px); }
          to   { opacity:1; transform:translateY(0); }
        }
        @keyframes kd-arrow-bob {
          0%,100% { transform:translateX(-50%) translateY(0);   opacity:.7; }
          50%      { transform:translateX(-50%) translateY(9px); opacity:1;  }
        }
        @keyframes kd-shimmer {
          0%,100% { opacity:0; transform:scaleX(1); }
          50%      { opacity:1; transform:scaleX(1.4); }
        }
      `}</style>

      <section
        id="section-splash"
        className="relative w-full overflow-hidden flex flex-col"
        style={{ height: '100svh' }}
      >
        {/* ── 하늘 그라디언트 ── */}
        <div
          className="absolute inset-0"
          style={{
            background:
              'linear-gradient(180deg, #6EC6F0 0%, #4AAEDC 18%, #2090C8 34%, #0A76AE 44%, #005A90 52%)',
          }}
        />

        {/* ── 바다 수심 그라디언트 ── */}
        <div
          className="absolute"
          style={{
            top: '50%', left: 0, right: 0, bottom: 0,
            background:
              'linear-gradient(180deg, #005A90 0%, #007EB5 12%, #009AC8 30%, #00B8D8 52%, #00D0E4 70%, #70E4F0 86%, #C0F2FA 100%)',
          }}
        />

        {/* ── 수평선 빛 번짐 ── */}
        <div
          className="absolute pointer-events-none"
          style={{
            top: '43%',
            left: 0,
            right: 0,
            height: '14%',
            background:
              'linear-gradient(180deg, rgba(180,236,255,0.0) 0%, rgba(180,236,255,0.22) 50%, rgba(180,236,255,0.0) 100%)',
          }}
        />

        {/* ── 수면 반짝임 ── */}
        {SHIMMERS.map((s, i) => (
          <div
            key={i}
            className="absolute pointer-events-none rounded-full"
            style={{
              top: s.top,
              left: s.left,
              width: s.w,
              height: s.h,
              background: 'rgba(255,255,255,0.95)',
              animation: `kd-shimmer ${s.dur} ease-in-out ${s.delay} infinite`,
              zIndex: 4,
            }}
          />
        ))}

        {/* ── 파도 레이어 4단 ── */}
        <div
          className="absolute pointer-events-none select-none"
          style={{ bottom: 0, left: 0, right: 0, height: '54%', zIndex: 2 }}
        >
          {/* 파도 1 — 먼 배경 (가장 느림) */}
          <svg
            className="absolute bottom-0 left-0"
            preserveAspectRatio="none"
            style={{ width: '200%', height: '100%', animation: 'kd-wave-a 16s linear infinite' }}
            viewBox="0 0 2880 340"
            xmlns="http://www.w3.org/2000/svg"
          >
            <defs>
              <linearGradient id="wg1" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%"   stopColor="#00A8D4" stopOpacity="0.85" />
                <stop offset="100%" stopColor="#00C8E4" stopOpacity="1"    />
              </linearGradient>
            </defs>
            {/* 비대칭 파도 (앞면 급경사) */}
            <path
              d="M0,190 C120,140 280,245 480,185 C660,130 840,250 1080,185
                 C1260,130 1440,245 1680,185 C1860,130 2040,250 2280,185
                 C2460,130 2640,245 2880,190 L2880,340 L0,340 Z"
              fill="url(#wg1)"
            />
            <path
              d="M0,185 C120,135 280,240 480,180 C660,125 840,245 1080,180
                 C1260,125 1440,240 1680,180 C1860,125 2040,245 2280,180
                 C2460,125 2640,240 2880,185"
              fill="none"
              stroke="rgba(255,255,255,0.30)"
              strokeWidth="7"
              strokeLinecap="round"
            />
          </svg>

          {/* 파도 2 — 중간 */}
          <svg
            className="absolute bottom-0 left-0"
            preserveAspectRatio="none"
            style={{ width: '200%', height: '100%', animation: 'kd-wave-b 10s linear infinite' }}
            viewBox="0 0 2880 340"
            xmlns="http://www.w3.org/2000/svg"
          >
            <defs>
              <linearGradient id="wg2" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%"   stopColor="#00C0DC" stopOpacity="0.9" />
                <stop offset="100%" stopColor="#50D8EC" stopOpacity="1"   />
              </linearGradient>
            </defs>
            <path
              d="M0,215 C100,155 260,270 500,205 C720,148 920,268 1160,205
                 C1360,148 1560,268 1800,205 C2000,148 2200,268 2440,205
                 C2620,148 2780,265 2880,215 L2880,340 L0,340 Z"
              fill="url(#wg2)"
            />
            {/* 두꺼운 폼 크레스트 */}
            <path
              d="M0,210 C100,150 260,265 500,200 C720,143 920,263 1160,200
                 C1360,143 1560,263 1800,200 C2000,143 2200,263 2440,200
                 C2620,143 2780,260 2880,210"
              fill="none"
              stroke="rgba(255,255,255,0.55)"
              strokeWidth="11"
              strokeLinecap="round"
            />
            <path
              d="M0,210 C100,150 260,265 500,200 C720,143 920,263 1160,200
                 C1360,143 1560,263 1800,200 C2000,143 2200,263 2440,200
                 C2620,143 2780,260 2880,210"
              fill="none"
              stroke="rgba(255,255,255,0.25)"
              strokeWidth="22"
              strokeLinecap="round"
            />
          </svg>

          {/* 파도 3 — 앞면 (하얀 크레스트 강조) */}
          <svg
            className="absolute bottom-0 left-0"
            preserveAspectRatio="none"
            style={{ width: '200%', height: '100%', animation: 'kd-wave-c 6.5s linear infinite' }}
            viewBox="0 0 2880 340"
            xmlns="http://www.w3.org/2000/svg"
          >
            <defs>
              <linearGradient id="wg3" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%"   stopColor="rgba(255,255,255,0.92)" />
                <stop offset="18%"  stopColor="#88EAF8"                />
                <stop offset="100%" stopColor="#A8F0FA"                />
              </linearGradient>
            </defs>
            <path
              d="M0,248 C80,195 220,280 420,238 C600,198 800,278 1040,235
                 C1240,196 1460,278 1680,238 C1880,196 2080,276 2320,235
                 C2520,196 2720,278 2880,245 L2880,340 L0,340 Z"
              fill="url(#wg3)"
            />
            {/* 파도 터지는 하얀 거품 */}
            <path
              d="M0,244 C80,191 220,276 420,234 C600,194 800,274 1040,231
                 C1240,192 1460,274 1680,234 C1880,192 2080,272 2320,231
                 C2520,192 2720,274 2880,241"
              fill="none"
              stroke="rgba(255,255,255,0.95)"
              strokeWidth="14"
              strokeLinecap="round"
            />
            <path
              d="M0,244 C80,191 220,276 420,234 C600,194 800,274 1040,231
                 C1240,192 1460,274 1680,234 C1880,192 2080,272 2320,231
                 C2520,192 2720,274 2880,241"
              fill="none"
              stroke="rgba(255,255,255,0.35)"
              strokeWidth="30"
              strokeLinecap="round"
            />
          </svg>

          {/* 파도 4 — 최전면 (얕은 물 & 흰 거품) */}
          <svg
            className="absolute bottom-0 left-0"
            preserveAspectRatio="none"
            style={{ width: '200%', height: '100%', animation: 'kd-wave-d 4s linear infinite' }}
            viewBox="0 0 2880 340"
            xmlns="http://www.w3.org/2000/svg"
          >
            <defs>
              <linearGradient id="wg4" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%"   stopColor="rgba(255,255,255,0.98)" />
                <stop offset="25%"  stopColor="rgba(210,248,255,0.92)" />
                <stop offset="100%" stopColor="rgba(185,242,252,0.88)" />
              </linearGradient>
            </defs>
            <path
              d="M0,285 C60,258 160,302 320,278 C480,255 660,300 860,272
                 C1040,248 1240,298 1440,272 C1640,248 1820,296 2020,268
                 C2220,244 2460,298 2660,270 C2780,255 2860,285 2880,278
                 L2880,340 L0,340 Z"
              fill="url(#wg4)"
            />
            <path
              d="M0,282 C60,255 160,299 320,275 C480,252 660,297 860,269
                 C1040,245 1240,295 1440,269 C1640,245 1820,293 2020,265
                 C2220,241 2460,295 2660,267 C2780,252 2860,282 2880,275"
              fill="none"
              stroke="rgba(255,255,255,0.98)"
              strokeWidth="18"
              strokeLinecap="round"
            />
            <path
              d="M0,282 C60,255 160,299 320,275 C480,252 660,297 860,269
                 C1040,245 1240,295 1440,269 C1640,245 1820,293 2020,265
                 C2220,241 2460,295 2660,267 C2780,252 2860,282 2880,275"
              fill="none"
              stroke="rgba(255,255,255,0.30)"
              strokeWidth="40"
              strokeLinecap="round"
            />
          </svg>
        </div>

        {/* ── Canvas 거품 파티클 ── */}
        <canvas
          ref={canvasRef}
          className="absolute inset-0 w-full h-full pointer-events-none"
          style={{ zIndex: 5 }}
        />

        {/* ── 텍스트 콘텐츠 (상단 하늘 영역) ── */}
        <div
          className="relative flex flex-col justify-center px-[clamp(32px,10vw,120px)]"
          style={{ height: '50%', zIndex: 10 }}
        >
          <h1
            className="font-serif leading-none mb-5"
            style={{
              fontSize: 'clamp(3.8rem,9.5vw,8rem)',
              color: '#ffffff',
              textShadow: '0 2px 24px rgba(0,60,140,0.35)',
              animation: mounted
                ? 'kd-fade-up 1s cubic-bezier(.22,1,.36,1) .15s both'
                : 'none',
              opacity: mounted ? undefined : 0,
            }}
          >
            K-Dive
          </h1>

          <p
            className="font-mono mb-3"
            style={{
              fontSize: 'clamp(.95rem,1.8vw,1.2rem)',
              color: 'rgba(255,255,255,0.92)',
              textShadow: '0 1px 10px rgba(0,50,120,0.4)',
              animation: mounted
                ? 'kd-fade-up 1s cubic-bezier(.22,1,.36,1) .65s both'
                : 'none',
              opacity: mounted ? undefined : 0,
            }}
          >
            Start with your vibe,
          </p>

          <p
            style={{
              fontSize: 'clamp(.82rem,1.1vw,.95rem)',
              lineHeight: 1.85,
              color: 'rgba(255,255,255,0.78)',
              maxWidth: 500,
              textShadow: '0 1px 8px rgba(0,40,100,0.35)',
              animation: mounted
                ? 'kd-fade-up 1s cubic-bezier(.22,1,.36,1) 1.05s both'
                : 'none',
              opacity: mounted ? undefined : 0,
            }}
          >
            K-Pop 음악에서 시작해 한국의 문화, 명소, 음식을 발견하는
            <br />
            새로운 방식의 한국 여행 큐레이션 플랫폼
          </p>

          <div
            className="mt-8 rounded-full"
            style={{
              width: 40,
              height: 3,
              background: 'rgba(255,255,255,0.55)',
              animation: mounted
                ? 'kd-fade-up 1s cubic-bezier(.22,1,.36,1) 1.35s both'
                : 'none',
              opacity: mounted ? undefined : 0,
            }}
          />
        </div>

        {/* ── 스크롤 화살표 ── */}
        <button
          type="button"
          onClick={scrollDown}
          aria-label="아래로 스크롤"
          className="absolute border-0 bg-transparent cursor-pointer p-2"
          style={{
            bottom: 28,
            left: '50%',
            zIndex: 10,
            animation: 'kd-arrow-bob 2.2s ease-in-out infinite',
          }}
        >
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
            <path
              d="M4 8L12 16L20 8"
              stroke="rgba(255,255,255,0.85)"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
      </section>
    </>
  );
}
