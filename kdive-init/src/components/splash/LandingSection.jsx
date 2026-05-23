'use client';

import { useEffect, useRef } from 'react';
import { useKdive } from '@/store/KdiveContext';


/* ─── 폰트 사이즈 토큰 ───────────────────────
   Head  36px | H1 28px | H2 20px | H3 16px | H4 12px
──────────────────────────────────────────── */

const FEATURES = [
  {
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M9 18V5l12-2v13" />
        <circle cx="6" cy="18" r="3" />
        <circle cx="18" cy="16" r="3" />
      </svg>
    ),
    title: 'Pick Your Track',
    desc: 'Choose three or more K-Pop tracks to define the mood of your trip.',
  },
  {
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z" />
        <circle cx="12" cy="9" r="2.5" />
      </svg>
    ),
    title: 'Discover Places',
    desc: 'Uncover hidden gems and must-see spots in Korea matched to your music vibe.',
  },
  {
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M18 8h1a4 4 0 0 1 0 8h-1" />
        <path d="M2 8h16v9a4 4 0 0 1-4 4H6a4 4 0 0 1-4-4V8z" />
        <line x1="6" y1="1" x2="6" y2="4" />
        <line x1="10" y1="1" x2="10" y2="4" />
        <line x1="14" y1="1" x2="14" y2="4" />
      </svg>
    ),
    title: 'Taste Local',
    desc: 'Experience the flavors of Korea with restaurant picks that match your atmosphere.',
  },
  {
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
      </svg>
    ),
    title: 'Surfy AI Guide',
    desc: 'Plan your perfect itinerary together with Surfy, your personal AI travel guide.',
  },
];

function useScrollReveal(ref) {
  useEffect(() => {
    if (!ref.current) return;
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add('kd-revealed');
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.12 }
    );
    ref.current.querySelectorAll('.kd-reveal').forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, [ref]);
}

export default function LandingSection() {
  const { loggedIn, showAuth, goGuest } = useKdive();
  const ref = useRef(null);
  useScrollReveal(ref);

  if (loggedIn) return null;

  return (
    <div ref={ref}>
      <style>{`
        .kd-reveal {
          opacity: 0;
          transform: translateY(28px);
          transition:
            opacity 0.9s cubic-bezier(0.16, 1, 0.3, 1),
            transform 0.9s cubic-bezier(0.16, 1, 0.3, 1);
        }
        .kd-reveal.kd-revealed {
          opacity: 1;
          transform: translateY(0);
        }
        @keyframes kd-surfer-float {
          0%, 100% { transform: translateY(0px) rotate(-2deg); }
          50%       { transform: translateY(-10px) rotate(2deg); }
        }
        @keyframes kd-surfer-shadow {
          0%, 100% { transform: scaleX(1);    opacity: 0.16; }
          50%       { transform: scaleX(0.65); opacity: 0.09; }
        }
      `}</style>

      {/* ── HOW IT WORKS 섹션 ── */}
      <section
        style={{
          padding: 'clamp(72px,10vh,120px) clamp(32px,10vw,120px)',
          background: '#ffffff',
        }}
      >
        <div style={{ maxWidth: 1160, margin: '0 auto' }}>

          {/* H4 — 12px */}
          <p
            className="kd-reveal font-mono"
            style={{
              fontSize: 12,
              letterSpacing: '0.15em',
              textTransform: 'uppercase',
              color: '#00A8E8',
              marginBottom: 18,
              transitionDelay: '0s',
            }}
          >
            How it works
          </p>

          {/* Head — 36px */}
          <h2
            className="kd-reveal font-serif"
            style={{
              fontSize: 36,
              lineHeight: 1.12,
              color: '#111111',
              marginBottom: 24,
              transitionDelay: '0.12s',
            }}
          >
            A Journey That<br />Begins With K-POP
          </h2>

          {/* 블록쿼트 — 노션/옵시디언 스타일 인용 */}
          <div
            className="kd-reveal"
            style={{
              borderLeft: '3px solid #00A8E8',
              paddingLeft: 20,
              maxWidth: 600,
              transitionDelay: '0.22s',
            }}
          >
            <p style={{ fontSize: 16, lineHeight: 1.85, color: '#888888' }}>
              One K-Pop song becomes the starting point of your adventure.
              We analyze the mood and essence of your favorite tracks to connect you
              with Korea&apos;s culture, landmarks, and local cuisine — a whole new
              way to travel.
            </p>
          </div>
        </div>
      </section>

      {/* ── YOUR JOURNEY WITH K-DIVE 섹션 ── */}
      <section
        style={{
          padding: 'clamp(0px,0vh,0px) clamp(32px,10vw,120px) clamp(72px,10vh,120px)',
          background: '#ffffff',
        }}
      >
        <div style={{ maxWidth: 1160, margin: '0 auto' }}>

          {/* 섹션 구분선 */}
          <div
            className="kd-reveal"
            style={{
              height: 1,
              background: 'rgba(0,0,0,0.07)',
              marginBottom: 'clamp(48px,7vh,80px)',
              transitionDelay: '0s',
            }}
          />

          {/* 블록쿼트 스타일로 감싼 H1 */}
          <div
            className="kd-reveal"
            style={{
              borderLeft: '3px solid #00A8E8',
              paddingLeft: 20,
              marginBottom: 'clamp(36px,5vh,56px)',
              transitionDelay: '0.12s',
            }}
          >
            <h2
              className="font-serif"
              style={{ fontSize: 28, color: '#111111' }}
            >
              Your Journey with K-Dive
            </h2>
          </div>

          {/* 피처 그리드 + 서퍼 — flex row로 세로 중앙 정렬 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 'clamp(24px,3vw,48px)' }}>

            {/* 피처 그리드 */}
            <div
              style={{
                flex: 1,
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
                gap: 'clamp(28px,3vw,44px)',
              }}
            >
              {FEATURES.map((f, i) => (
                <div
                  key={i}
                  className="kd-reveal"
                  style={{
                    transitionDelay: `${i * 0.1}s`,
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 12,
                  }}
                >
                  {/* 아이콘 박스 */}
                  <div
                    style={{
                      width: 48,
                      height: 48,
                      borderRadius: 12,
                      background: 'rgba(0,168,232,0.1)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: '#00A8E8',
                      flexShrink: 0,
                    }}
                  >
                    {f.icon}
                  </div>

                  {/* H2 — 20px */}
                  <h3
                    className="font-serif"
                    style={{ fontSize: 20, color: '#111111', lineHeight: 1.2 }}
                  >
                    {f.title}
                  </h3>

                  {/* H3 — 16px */}
                  <p style={{ fontSize: 16, lineHeight: 1.7, color: '#888888' }}>
                    {f.desc}
                  </p>
                </div>
              ))}
            </div>

            {/* 서퍼 캐릭터 — 피처 그리드와 세로 중앙 정렬 */}
            <div
              className="kd-reveal"
              style={{
                flexShrink: 0,
                transitionDelay: '0.42s',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: 8,
              }}
            >
              {/* 말풍선 */}
              <div
                style={{
                  background: '#ffffff',
                  border: '1px solid rgba(0,0,0,0.08)',
                  borderRadius: 16,
                  padding: '8px 16px',
                  fontSize: 12,       /* H4 */
                  color: 'rgba(0,0,0,0.55)',
                  lineHeight: 1.4,
                  textAlign: 'center',
                  boxShadow: '0 4px 16px rgba(0,0,0,0.06)',
                  whiteSpace: 'nowrap',
                }}
              >
                Surfy with me?
              </div>

              {/* 서퍼 SVG */}
              <div style={{ animation: 'kd-surfer-float 3.4s ease-in-out infinite' }}>
                <svg
                  aria-hidden="true"
                  viewBox="0 0 88 104"
                  style={{ width: 64, height: 76, overflow: 'visible' }}
                >
                  <defs>
                    <linearGradient id="landingSurferFill" x1="17" y1="10" x2="72" y2="96" gradientUnits="userSpaceOnUse">
                      <stop stopColor="#00a8e8" />
                      <stop offset="1" stopColor="#006fe8" />
                    </linearGradient>
                  </defs>
                  <path
                    d="M44 10C62 10 74 24 74 43V55C74 65 68 72 60 72C57 72 55 70 54 66C52 74 48 80 44 80C40 80 36 74 34 66C33 70 31 72 28 72C20 72 14 65 14 55V43C14 24 26 10 44 10Z"
                    fill="url(#landingSurferFill)"
                  />
                  <ellipse cx="34" cy="28" rx="3.2" ry="5.0" fill="#ffffff" />
                  <ellipse cx="54" cy="28" rx="3.2" ry="5.0" fill="#ffffff" />
                  <circle cx="44" cy="39" r="1.9" fill="#ffffff" />
                </svg>
              </div>

              {/* 그림자 */}
              <div
                style={{
                  width: 40,
                  height: 7,
                  borderRadius: '50%',
                  background: 'rgba(0,100,160,0.14)',
                  animation: 'kd-surfer-shadow 3.4s ease-in-out infinite',
                }}
              />
            </div>
          </div>

          {/* ── CTA 버튼 ── */}
          <div
            className="kd-reveal"
            style={{
              marginTop: 'clamp(48px,7vh,72px)',
              display: 'flex',
              gap: 12,
              flexWrap: 'wrap',
              transitionDelay: '0.5s',
            }}
          >
            <button
              type="button"
              onClick={() => showAuth('login')}
              style={{
                height: 50,
                padding: '0 28px',
                borderRadius: 999,
                border: 'none',
                background: 'linear-gradient(135deg, #00A8E8, #006FE8)',
                color: '#ffffff',
                fontSize: 15,
                fontWeight: 700,
                cursor: 'pointer',
                letterSpacing: '0.02em',
                transition: 'opacity 0.15s, transform 0.15s',
              }}
              onMouseEnter={(e) => { e.currentTarget.style.opacity = '0.88'; e.currentTarget.style.transform = 'translateY(-2px)'; }}
              onMouseLeave={(e) => { e.currentTarget.style.opacity = '1'; e.currentTarget.style.transform = 'translateY(0)'; }}
            >
              로그인하기
            </button>

            <button
              type="button"
              onClick={() => showAuth('signup')}
              style={{
                height: 50,
                padding: '0 28px',
                borderRadius: 999,
                border: '1.5px solid #00A8E8',
                background: 'transparent',
                color: '#00A8E8',
                fontSize: 15,
                fontWeight: 700,
                cursor: 'pointer',
                letterSpacing: '0.02em',
                transition: 'background 0.15s, transform 0.15s',
              }}
              onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(0,168,232,0.06)'; e.currentTarget.style.transform = 'translateY(-2px)'; }}
              onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.transform = 'translateY(0)'; }}
            >
              회원가입하기
            </button>

            <button
              type="button"
              onClick={goGuest}
              style={{
                height: 50,
                padding: '0 24px',
                borderRadius: 999,
                border: '1.5px solid rgba(0,0,0,0.12)',
                background: 'transparent',
                color: '#888888',
                fontSize: 14,
                fontWeight: 500,
                cursor: 'pointer',
                letterSpacing: '0.01em',
                transition: 'color 0.15s, border-color 0.15s, transform 0.15s',
              }}
              onMouseEnter={(e) => { e.currentTarget.style.color = '#444'; e.currentTarget.style.borderColor = 'rgba(0,0,0,0.25)'; e.currentTarget.style.transform = 'translateY(-2px)'; }}
              onMouseLeave={(e) => { e.currentTarget.style.color = '#888888'; e.currentTarget.style.borderColor = 'rgba(0,0,0,0.12)'; e.currentTarget.style.transform = 'translateY(0)'; }}
            >
              비회원으로 이용하기
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}
