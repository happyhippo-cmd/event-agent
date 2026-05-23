'use client';

// 결과 이미지 위에 한국어 손글씨 폰트(Nanum Pen Script / Gaegu)로
// title + memos 를 SVG 텍스트로 흩뿌려 오버레이.
// 이미지 모델은 글자를 안 그리고, 진짜 한글 폰트가 또렷이 보임 → 깨짐 0.

import { useMemo } from 'react';

/**
 * @typedef {Object} Placement
 * @property {number} x        0~100 (%)
 * @property {number} y        0~100 (%)
 * @property {number} rotate   deg
 * @property {number} fontSize px (1000 기준)
 * @property {("pen" | "gaegu")} font
 * @property {("start" | "middle" | "end")} align
 */

// 메모를 흩뿌릴 anchor 좌표 (가장자리 위주)
const ANCHORS = [
  { x: 6, y: 10, rotate: -4, align: 'start' },     // 좌상단
  { x: 94, y: 12, rotate: 3, align: 'end' },       // 우상단
  { x: 50, y: 7, rotate: -2, align: 'middle' },    // 상단 중앙
  { x: 6, y: 50, rotate: -6, align: 'start' },     // 좌측 중앙
  { x: 94, y: 48, rotate: 5, align: 'end' },       // 우측 중앙
  { x: 8, y: 88, rotate: 3, align: 'start' },      // 좌하단
  { x: 92, y: 90, rotate: -4, align: 'end' },      // 우하단
  { x: 50, y: 94, rotate: 2, align: 'middle' },    // 하단 중앙
  { x: 26, y: 22, rotate: -3, align: 'start' },
  { x: 74, y: 26, rotate: 2, align: 'end' },
  { x: 28, y: 78, rotate: 4, align: 'start' },
  { x: 72, y: 80, rotate: -3, align: 'end' },
];

function placementsFor(count) {
  return ANCHORS.slice(0, count).map((a, i) => ({
    ...a,
    fontSize: 22 + (i % 3) * 3, // 22 / 25 / 28 px (1000 기준)
    font: i % 4 === 0 ? 'gaegu' : 'pen',
  }));
}

/**
 * @param {Object} props
 * @param {string} props.src        결과 이미지 (data URL 또는 url)
 * @param {string} [props.title]
 * @param {string[]} props.memos
 * @param {string} [props.alt]
 * @param {string} [props.className]
 */
export default function HandwrittenOverlay({
  src,
  title,
  memos,
  alt = 'generated',
  className = '',
}) {
  const placements = useMemo(() => placementsFor(memos.length), [memos.length]);

  return (
    <div
      className={`relative inline-block max-w-full ${className}`}
      style={{ lineHeight: 0 }}
    >
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={src}
        alt={alt}
        className="block h-auto max-h-full max-w-full"
      />

      <svg
        className="pointer-events-none absolute inset-0 h-full w-full"
        viewBox="0 0 1000 1000"
        preserveAspectRatio="none"
        aria-hidden
      >
        <defs>
          {/* 흰 글씨에 살짝 어두운 그림자(가독성) */}
          <filter id="hw-shadow" x="-20%" y="-20%" width="140%" height="140%">
            <feDropShadow dx="0" dy="1" stdDeviation="1.2" floodOpacity="0.5" />
          </filter>
        </defs>

        {/* 메인 타이틀 — 사진 상단 살짝 좌측에 큰 손글씨로 */}
        {title && (
          <text
            x={60}
            y={90}
            fontFamily="'Nanum Pen Script', cursive"
            fontSize={62}
            fill="white"
            transform="rotate(-3 60 90)"
            filter="url(#hw-shadow)"
          >
            {title}
          </text>
        )}

        {/* 메모들 */}
        {memos.map((memo, i) => {
          const p = placements[i];
          if (!p) return null;
          const cx = (p.x / 100) * 1000;
          const cy = (p.y / 100) * 1000;
          const fontFamily =
            p.font === 'gaegu'
              ? "'Gaegu', cursive"
              : "'Nanum Pen Script', cursive";
          return (
            <text
              key={i}
              x={cx}
              y={cy}
              fontFamily={fontFamily}
              fontSize={p.fontSize}
              fill="white"
              textAnchor={p.align}
              transform={`rotate(${p.rotate} ${cx} ${cy})`}
              filter="url(#hw-shadow)"
            >
              {memo}
            </text>
          );
        })}
      </svg>
    </div>
  );
}