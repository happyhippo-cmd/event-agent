'use client';

import { useEffect, useRef, useState } from 'react';

export default function SurferGuideCharacter({ onClick }) {
  const guideRef = useRef(null);
  const characterRef = useRef(null);
  const animationRef = useRef(null);
  const [isGuiding, setIsGuiding] = useState(false);

  useEffect(() => {
    // 매 pointermove 이벤트마다 getBoundingClientRect + setProperty x4를 실행하면 layout thrash가
    // 일어날 수 있어, 마지막 좌표만 다음 프레임에 한 번 적용하도록 rAF 코얼레싱.
    let latestX = 0;
    let latestY = 0;
    let rafId = 0;

    const applyLatest = () => {
      rafId = 0;
      const node = characterRef.current;
      if (!node) return;
      const rect = node.getBoundingClientRect();
      const centerX = rect.left + rect.width / 2;
      const centerY = rect.top + rect.height * 0.42;
      const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
      const eyeX = clamp((latestX - centerX) / 140, -1, 1) * 3.2;
      const eyeY = clamp((latestY - centerY) / 120, -1, 1) * 2.4;
      const mouthX = eyeX * 0.42;
      const mouthY = eyeY * 0.32;
      node.style.setProperty('--surfy-eye-x', `${eyeX}px`);
      node.style.setProperty('--surfy-eye-y', `${eyeY}px`);
      node.style.setProperty('--surfy-mouth-x', `${mouthX}px`);
      node.style.setProperty('--surfy-mouth-y', `${mouthY}px`);
    };

    const handlePointerMove = (event) => {
      latestX = event.clientX;
      latestY = event.clientY;
      if (rafId) return;
      rafId = window.requestAnimationFrame(applyLatest);
    };

    window.addEventListener('pointermove', handlePointerMove);
    return () => {
      window.removeEventListener('pointermove', handlePointerMove);
      if (rafId) window.cancelAnimationFrame(rafId);
    };
  }, []);

  useEffect(() => () => {
    animationRef.current?.cancel();
  }, []);

  const handleGuideClick = () => {
    const guide = guideRef.current;
    const character = characterRef.current;
    const surfyNavButton = document.querySelector('[data-nav-target="surfy"]');
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    if (isGuiding) return;
    if (!guide || !character || !surfyNavButton || prefersReducedMotion) {
      onClick();
      return;
    }

    const characterRect = character.getBoundingClientRect();
    const navRect = surfyNavButton.getBoundingClientRect();
    const startX = characterRect.left + characterRect.width / 2;
    const startY = characterRect.top + characterRect.height / 2;
    const endX = navRect.left + navRect.width / 2;
    const endY = navRect.top + navRect.height / 2;
    const dx = endX - startX;
    const dy = endY - startY;
    const waveX = Math.min(86, Math.max(42, window.innerWidth * 0.045));

    setIsGuiding(true);
    animationRef.current?.cancel();
    animationRef.current = guide.animate(
      [
        { transform: 'translate3d(0, 0, 0) scale(1)', offset: 0 },
        { transform: `translate3d(${dx * 0.08}px, ${dy * 0.12}px, 0) scale(1.02)`, offset: 0.1 },
        { transform: `translate3d(${dx * 0.2 - waveX * 0.28}px, ${dy * 0.32}px, 0) scale(1.02)`, offset: 0.27 },
        { transform: `translate3d(${dx * 0.45 + waveX}px, ${dy * 0.52}px, 0) scale(1)`, offset: 0.48 },
        { transform: `translate3d(${dx * 0.7 - waveX * 0.58}px, ${dy * 0.72}px, 0) scale(0.96)`, offset: 0.68 },
        { transform: `translate3d(${dx * 0.9 + waveX * 0.2}px, ${dy * 0.9}px, 0) scale(0.9)`, offset: 0.86 },
        { transform: `translate3d(${dx}px, ${dy}px, 0) scale(0.82)`, offset: 1 },
      ],
      {
        duration: 1850,
        easing: 'cubic-bezier(0.2, 0.74, 0.22, 1)',
        fill: 'forwards',
      }
    );

    animationRef.current.onfinish = () => {
      setIsGuiding(false);
      animationRef.current = null;
      onClick();
    };
    animationRef.current.oncancel = () => {
      setIsGuiding(false);
      animationRef.current = null;
    };
  };

  return (
    <div
      ref={guideRef}
      className={`kd-surfy-guide fixed bottom-8 right-9 h-[86px] w-[166px] max-[760px]:bottom-5 max-[760px]:right-3 max-[760px]:h-[80px] max-[760px]:w-[150px] ${isGuiding ? 'is-guiding z-[120]' : 'z-30'}`}
    >
      <div className="kd-surfy-guide-bubble pointer-events-none absolute bottom-[58px] right-[-22px] flex w-[176px] items-center justify-center rounded-[20px] border border-[rgba(0,0,0,0.08)] bg-white px-5 py-2.5 text-center text-[12px] leading-[1.45] text-black/65 max-[760px]:bottom-[54px] max-[760px]:right-[-18px] max-[760px]:w-[168px]">
        Surfy with me?
      </div>
      <button
        type="button"
        ref={characterRef}
        onClick={handleGuideClick}
        disabled={isGuiding}
        aria-label="Surfer와 장소 더 찾기"
        className="kd-surfy-guide-character absolute bottom-0 right-2 flex h-[48px] w-[40px] items-center justify-center border-0 bg-transparent p-0 text-text transition-transform hover:scale-[1.06] focus:outline-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent max-[760px]:h-[46px] max-[760px]:w-[39px]"
      >
        <svg aria-hidden="true" viewBox="0 0 88 104" className="h-full w-full overflow-visible">
          <defs>
            <linearGradient id="surferGuideActiveFill" x1="17" y1="10" x2="72" y2="96" gradientUnits="userSpaceOnUse">
              <stop stopColor="#00a8e8" />
              <stop offset="1" stopColor="#006fe8" />
            </linearGradient>
          </defs>
          <path
            d="M44 10C62 10 74 24 74 43V55C74 65 68 72 60 72C57 72 55 70 54 66C52 74 48 80 44 80C40 80 36 74 34 66C33 70 31 72 28 72C20 72 14 65 14 55V43C14 24 26 10 44 10Z"
            fill="url(#surferGuideActiveFill)"
          />
          <g className="kd-surfy-guide-eyes">
            <g>
              <ellipse className="kd-surfy-guide-eye-dot" cx="34" cy="28" rx="3.2" ry="5.0" fill="#ffffff" />
            </g>
            <g>
              <ellipse className="kd-surfy-guide-eye-dot" cx="54" cy="28" rx="3.2" ry="5.0" fill="#ffffff" />
            </g>
          </g>
          <g className="kd-surfy-guide-mouth">
            <circle className="kd-surfy-guide-mouth-dot" cx="44" cy="39" r="1.9" fill="#ffffff" />
            <path
              className="kd-surfy-guide-mouth-open"
              d="M40.2 33.5Q44 37.5 47.8 33.5Q46.2 39.2 44 40.2Q41.8 39.2 40.2 33.5Z"
              fill="#ffffff"
            />
          </g>
        </svg>
      </button>
    </div>
  );
}
