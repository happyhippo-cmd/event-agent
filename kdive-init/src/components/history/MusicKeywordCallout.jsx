'use client';

export default function MusicKeywordCallout({ tracks }) {
  if (!tracks.length) return null;
  const keywordText = tracks.map((track) => track.title).join(' · ');
  // 키워드 문자열 길이에 비례해 duration을 정해, 키워드가 짧을 때 너무 빨라지지 않도록 하한 적용.
  // (대략 0.5s/char, 최소 20s)
  const durationSeconds = Math.max(20, keywordText.length * 0.5);

  return (
    <aside className="ml-2.5 mr-3 flex min-h-[32px] items-center max-[760px]:mx-0 max-[760px]:w-full max-[760px]:items-start">
      <div className="flex min-w-0 flex-1 items-center gap-3 overflow-hidden max-[760px]:flex-col max-[760px]:items-start max-[760px]:gap-1">
        <span className="flex-shrink-0 text-[12px] font-bold uppercase tracking-[0.12em] text-accent">
          Music Keywords
        </span>
        <div className="kd-history-keyword-marquee min-w-0 flex-1 overflow-hidden text-[14px] leading-[1.5] text-black/60">
          <span
            className="kd-history-keyword-track"
            style={{ '--marquee-duration': `${durationSeconds}s` }}
          >
            <span>{keywordText}{' · '}</span>
            <span aria-hidden="true">{keywordText}{' · '}</span>
          </span>
        </div>
      </div>
    </aside>
  );
}
