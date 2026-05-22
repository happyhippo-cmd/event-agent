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
      y:    h * 0.58 + Math.random() * h * 0.42,
      r:    0.7 + Math.random() * 3.2,
      op:   0.2  + Math.random() * 0.5,
      vx:   (Math.random() - 0.5) * 0.5,
      vy:   -0.1 - Math.random() * 0.6,
      life: 0,
      max:  80 + Math.random() * 120,
    });

    const W = () => canvas.width;
    const H = () => canvas.height;
    const particles = Array.from({ length: 85 }, () => {
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
        @keyframes kd-wave-c {
          from { transform: translateX(-5%); }
          to   { transform: translateX(-55%); }
        }
        @keyframes kd-wave-d {
          from { transform: translateX(-22%); }
          to   { transform: translateX(-72%); }
        }
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
        {/* ─────────────────────────────────────
            레이어 0: CSS 폴백 배경
            (비디오 로드 전 / 파일 없을 때 표시)
        ───────────────────────────────────── */}
        <div
          className="absolute inset-0"
          style={{
            background:
              'linear-gradient(180deg, #6EC6F0 0%, #4AAEDC 18%, #2090C8 34%,' +
              '#0A76AE 44%, #005A90 52%, #007EB5 62%, #00B8D8 78%, #70E4F0 92%, #C0F2FA 100%)',
            zIndex: 0,
          }}
        />

        {/* ─────────────────────────────────────
            레이어 1: 실사 비디오 배경

            📁 영상 위치: kdive-init/public/videos/ocean.mp4
            🎬 무료 영상 다운로드:
               https://mixkit.co/free-stock-video/ocean/
               → "Waves Breaking on the Shore" 류 선택
               → 1080p MP4 다운로드 후 ocean.mp4 로 저장
        ───────────────────────────────────── */}
        <video
          autoPlay
          muted
          loop
          playsInline
          className="absolute inset-0 w-full h-full"
          style={{
            zIndex: 1,
            objectFit: 'cover',
            filter: 'brightness(0.88) saturate(1.15)',
          }}
        >
          <source src="/videos/ocean.mp4" type="video/mp4" />
          {/* webm 포맷도 있다면 화질/용량 유리 */}
          {/* <source src="/videos/ocean.webm" type="video/webm" /> */}
        </video>

        {/* ─────────────────────────────────────
            레이어 2: 텍스트 가독성 오버레이
            (좌측 영역만 살짝 어둡게)
        ───────────────────────────────────── */}
        <div
          className="absolute inset-0"
          style={{
            background:
              'linear-gradient(108deg, rgba(0,18,65,0.55) 0%, rgba(0,18,65,0.28) 42%, transparent 72%)',
            zIndex: 2,
          }}
        />

        {/* ─────────────────────────────────────
            레이어 3: 하단 파도 블렌딩 (영상 경계 자연스럽게)
        ───────────────────────────────────── */}
        <div
          className="absolute bottom-0 left-0 right-0 pointer-events-none"
          style={{
            height: '28%',
            background: 'linear-gradient(to bottom, transparent, rgba(0,150,200,0.22))',
            zIndex: 3,
          }}
        />

        {/* ─────────────────────────────────────
            레이어 4: SVG 파도 2단 (하단 엣지)
        ───────────────────────────────────── */}
        <div
          className="absolute pointer-events-none select-none"
          style={{ bottom: 0, left: 0, right: 0, height: '26%', zIndex: 4 }}
        >
          {/* 파도 A — 크레스트 */}
          <svg
            className="absolute bottom-0 left-0"
            preserveAspectRatio="none"
            style={{ width: '200%', height: '100%', animation: 'kd-wave-c 7s linear infinite' }}
            viewBox="0 0 2880 200"
            xmlns="http://www.w3.org/2000/svg"
          >
            <defs>
              <linearGradient id="wgA" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%"   stopColor="rgba(255,255,255,0.38)" />
                <stop offset="100%" stopColor="rgba(255,255,255,0.08)" />
              </linearGradient>
            </defs>
            <path
              d="M0,100 C80,65 220,135 420,98 C600,64 800,132 1040,95
                 C1240,62 1460,130 1680,96 C1880,63 2080,128 2320,94
                 C2520,62 2720,130 2880,100 L2880,200 L0,200 Z"
              fill="url(#wgA)"
            />
            <path
              d="M0,96 C80,61 220,131 420,94 C600,60 800,128 1040,91
                 C1240,58 1460,126 1680,92 C1880,59 2080,124 2320,90
                 C2520,58 2720,126 2880,96"
              fill="none"
              stroke="rgba(255,255,255,0.72)"
              strokeWidth="10"
              strokeLinecap="round"
            />
            <path
              d="M0,96 C80,61 220,131 420,94 C600,60 800,128 1040,91
                 C1240,58 1460,126 1680,92 C1880,59 2080,124 2320,90
                 C2520,58 2720,126 2880,96"
              fill="none"
              stroke="rgba(255,255,255,0.18)"
              strokeWidth="26"
              strokeLinecap="round"
            />
          </svg>

          {/* 파도 B — 최전면 하얀 거품 */}
          <svg
            className="absolute bottom-0 left-0"
            preserveAspectRatio="none"
            style={{ width: '200%', height: '100%', animation: 'kd-wave-d 4.2s linear infinite' }}
            viewBox="0 0 2880 200"
            xmlns="http://www.w3.org/2000/svg"
          >
            <defs>
              <linearGradient id="wgB" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%"   stopColor="rgba(255,255,255,0.58)" />
                <stop offset="100%" stopColor="rgba(210,245,255,0.28)" />
              </linearGradient>
            </defs>
            <path
              d="M0,140 C60,112 160,158 320,132 C480,108 660,154 860,126
                 C1040,104 1240,152 1440,126 C1640,104 1820,150 2020,122
                 C2220,100 2460,150 2660,124 C2780,108 2860,138 2880,132
                 L2880,200 L0,200 Z"
              fill="url(#wgB)"
            />
            <path
              d="M0,137 C60,109 160,155 320,129 C480,105 660,151 860,123
                 C1040,101 1240,149 1440,123 C1640,101 1820,147 2020,119
                 C2220,97 2460,147 2660,121 C2780,105 2860,135 2880,129"
              fill="none"
              stroke="rgba(255,255,255,0.95)"
              strokeWidth="14"
              strokeLinecap="round"
            />
            <path
              d="M0,137 C60,109 160,155 320,129 C480,105 660,151 860,123
                 C1040,101 1240,149 1440,123 C1640,101 1820,147 2020,119
                 C2220,97 2460,147 2660,121 C2780,105 2860,135 2880,129"
              fill="none"
              stroke="rgba(255,255,255,0.22)"
              strokeWidth="36"
              strokeLinecap="round"
            />
          </svg>
        </div>

        {/* 레이어 5: Canvas 거품 파티클 */}
        <canvas
          ref={canvasRef}
          className="absolute inset-0 w-full h-full pointer-events-none"
          style={{ zIndex: 5 }}
        />

        {/* 레이어 6: 수면 반짝임 */}
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

        {/* ─────────────────────────────────────
            레이어 10: 텍스트 콘텐츠
        ───────────────────────────────────── */}
        <div
          className="relative flex flex-col justify-center px-[clamp(32px,10vw,120px)]"
          style={{ height: '52%', zIndex: 10 }}
        >
          <h1
            className="font-serif leading-none mb-5"
            style={{
              fontSize: 'clamp(3.8rem,9.5vw,8rem)',
              color: '#ffffff',
              textShadow: '0 2px 28px rgba(0,20,80,0.55), 0 4px 64px rgba(0,10,50,0.3)',
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
              color: 'rgba(255,255,255,0.95)',
              textShadow: '0 1px 12px rgba(0,20,80,0.5)',
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
              color: 'rgba(255,255,255,0.82)',
              maxWidth: 500,
              textShadow: '0 1px 8px rgba(0,15,70,0.4)',
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
              width: 40, height: 3,
              background: 'rgba(255,255,255,0.6)',
              animation: mounted
                ? 'kd-fade-up 1s cubic-bezier(.22,1,.36,1) 1.35s both'
                : 'none',
              opacity: mounted ? undefined : 0,
            }}
          />
        </div>

        {/* 스크롤 화살표 */}
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
