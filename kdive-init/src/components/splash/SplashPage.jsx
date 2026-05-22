'use client';

import { useEffect, useRef, useState } from 'react';
import { useKdive } from '@/store/KdiveContext';

/* ─────────────────────────────────────────────
   Canvas 거품 파티클
───────────────────────────────────────────── */
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

    const mkP = (w, h) => ({
      x:    Math.random() * w,
      y:    h * 0.6 + Math.random() * h * 0.4,
      r:    0.7 + Math.random() * 3,
      op:   0.3 + Math.random() * 0.55,
      vx:   (Math.random() - 0.5) * 0.45,
      vy:   -0.1 - Math.random() * 0.55,
      life: 0,
      max:  80 + Math.random() * 120,
    });

    const W = () => canvas.width;
    const H = () => canvas.height;
    const particles = Array.from({ length: 90 }, () => {
      const p = mkP(canvas.width, canvas.height);
      p.life = Math.random() * p.max;
      return p;
    });

    let rafId;
    const tick = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      particles.forEach((p, i) => {
        p.life++;
        if (p.life >= p.max) { particles[i] = mkP(W(), H()); return; }
        p.x += p.vx;
        p.y += p.vy;
        const alpha = p.op * Math.sin((p.life / p.max) * Math.PI);
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(255,255,255,${alpha.toFixed(3)})`;
        ctx.fill();
      });
      rafId = requestAnimationFrame(tick);
    };
    tick();

    return () => { cancelAnimationFrame(rafId); ro.disconnect(); };
  }, [canvasRef]);
}

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
        @keyframes kd-fade-up {
          from { opacity: 0; transform: translateY(22px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        @keyframes kd-arrow-bob {
          0%,100% { transform: translateX(-50%) translateY(0);   opacity: .7; }
          50%      { transform: translateX(-50%) translateY(9px); opacity: 1;  }
        }
        @keyframes kd-shimmer {
          0%,100% { opacity: 0; transform: scaleX(1);   }
          50%      { opacity: 1; transform: scaleX(1.4); }
        }
      `}</style>

      <section
        id="section-splash"
        className="relative w-full overflow-hidden"
        style={{ height: '100svh' }}
      >
        {/* ── 레이어 0: CSS 폴백 배경 ── */}
        <div
          className="absolute inset-0"
          style={{
            background:
              'linear-gradient(180deg,#6EC6F0 0%,#4AAEDC 18%,#2090C8 34%,' +
              '#0A76AE 44%,#005A90 52%,#007EB5 62%,#00B8D8 78%,#70E4F0 92%,#C0F2FA 100%)',
            zIndex: 0,
          }}
        />

        {/* ── 레이어 1: 실사 비디오 — filter 없음 (원본 컬러) ── */}
        <video
          autoPlay
          muted
          loop
          playsInline
          className="absolute inset-0 w-full h-full"
          style={{ zIndex: 1, objectFit: 'cover' }}
        >
          <source src="/videos/ocean.mp4" type="video/mp4" />
        </video>

        {/* ── 레이어 2: 텍스트 가독성 오버레이 (좌측만 살짝) ── */}
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

        {/* ── 레이어 5: Canvas 거품 파티클 ── */}
        <canvas
          ref={canvasRef}
          className="absolute inset-0 w-full h-full pointer-events-none"
          style={{ zIndex: 5 }}
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

        {/* ── 레이어 10: 텍스트 ── */}
        <div
          className="relative flex flex-col justify-center px-[clamp(32px,10vw,120px)]"
          style={{ height: '52%', zIndex: 10 }}
        >
          <h1
            className="font-serif leading-none mb-5"
            style={{
              fontSize: 'clamp(3.8rem,9.5vw,8rem)',
              color: '#ffffff',
              textShadow: '0 2px 28px rgba(0,20,80,0.55),0 4px 64px rgba(0,10,50,0.3)',
              animation: mounted ? 'kd-fade-up 1s cubic-bezier(.22,1,.36,1) .15s both' : 'none',
              opacity: mounted ? undefined : 0,
            }}
          >
            K-Dive
          </h1>

          <p
            className="font-mono mb-3"
            style={{
              fontSize: 'clamp(.95rem,1.8vw,1.2rem)',
              color: 'rgba(255,255,255,0.95)',
              textShadow: '0 1px 12px rgba(0,20,80,0.5)',
              animation: mounted ? 'kd-fade-up 1s cubic-bezier(.22,1,.36,1) .65s both' : 'none',
              opacity: mounted ? undefined : 0,
            }}
          >
            Start with your vibe,
          </p>

          <p
            style={{
              fontSize: 'clamp(.82rem,1.1vw,.95rem)',
              lineHeight: 1.85,
              color: 'rgba(255,255,255,0.82)',
              maxWidth: 500,
              textShadow: '0 1px 8px rgba(0,15,70,0.4)',
              animation: mounted ? 'kd-fade-up 1s cubic-bezier(.22,1,.36,1) 1.05s both' : 'none',
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
              width: 40, height: 3,
              background: 'rgba(255,255,255,0.6)',
              animation: mounted ? 'kd-fade-up 1s cubic-bezier(.22,1,.36,1) 1.35s both' : 'none',
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
            bottom: 28, left: '50%', zIndex: 10,
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
