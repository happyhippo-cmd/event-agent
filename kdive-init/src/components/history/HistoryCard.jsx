'use client';

import RoundActionButton from '@/components/common/RoundActionButton';
import { getCurationText } from './historyItems';

export function EmptyCard({ index }) {
  return (
    <div
      aria-hidden="true"
      className="h-[156px] rounded-[18px] border border-[rgba(0,0,0,0.08)] bg-white shadow-[4px_4px_4px_rgba(0,0,0,0.02)]"
    >
      <span className="sr-only">empty history slot {index + 1}</span>
    </div>
  );
}

export function ComingSoonCard({ label }) {
  return (
    <div className="h-[156px] rounded-[18px] border border-[rgba(0,0,0,0.08)] bg-white p-5 shadow-[4px_4px_4px_rgba(0,0,0,0.02)]">
      <div className="flex h-full flex-col justify-between">
        <span className="text-[12px] font-bold uppercase tracking-[0.12em] text-accent">{label}</span>
        <p className="text-[14px] leading-[1.6] text-muted">
          온보딩에서 저장한 기록을 바탕으로 채워질 영역이에요.
        </p>
      </div>
    </div>
  );
}

export function HistoryCard({ item, liked, visited, curationOpen, onUnlike, onToggleVisited, onToggleCuration }) {
  const canMarkVisited = item.type !== 'track';

  return (
    <article className={`kd-history-card relative min-h-[156px] overflow-hidden rounded-[18px] border bg-white p-px shadow-[4px_4px_4px_rgba(0,0,0,0.02)] transition-colors duration-150 ${curationOpen ? 'border-accent-border' : 'border-[rgba(0,0,0,0.08)]'}`}>
      <div className="relative z-[1] flex min-h-[154px] flex-col rounded-[17px] bg-white p-4 pb-3">
        <div className="flex h-6 items-center justify-between gap-3">
          <span aria-hidden="true" className="flex h-6 w-6 flex-shrink-0 items-center justify-center text-[16px] leading-none">{item.emoji}</span>
          <div className="flex flex-shrink-0 items-center gap-1.5">
            <RoundActionButton
              variant="like"
              active={liked}
              label={`${item.title} ${liked ? '좋아요 삭제 예약' : '좋아요 유지'}`}
              onClick={() => onUnlike(item)}
              className="h-6 w-6 text-[22px]"
            />
            {canMarkVisited ? (
              <RoundActionButton
                variant="visited"
                active={visited}
                label={`${item.title} ${visited ? '방문 완료 취소' : '방문 완료로 표시'}`}
                onClick={() => onToggleVisited(item)}
                className="h-5 w-5 text-[14px]"
              />
            ) : null}
          </div>
        </div>

        <div className="mt-3 min-w-0 text-text">
          <h3 className="kd-history-card-title font-pretendard text-[16px] font-semibold leading-[1.35]">{item.title}</h3>
          <p className="mt-1 flex min-w-0 items-center text-[14px] text-muted">
            <span className="truncate">{item.subtitle}</span>
          </p>
        </div>

        <div className="mt-8">
          <button
            type="button"
            onClick={() => onToggleCuration(item)}
            aria-expanded={curationOpen}
            className="flex w-full cursor-pointer items-center justify-between border-0 bg-transparent text-left text-[14px] font-medium text-muted focus:outline-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
          >
            <span className="tracking-[0.08em]">Curation</span>
            <span className={`flex h-6 w-6 items-center justify-center transition-transform ${curationOpen ? 'rotate-180 text-accent-border' : 'text-muted'}`}>⌄</span>
          </button>

          <div className={`kd-history-curation ${curationOpen ? 'is-open' : ''}`} aria-hidden={!curationOpen}>
            <div>
              <p className="mt-2 border-t border-[rgba(0,0,0,0.08)] pt-3 text-[14px] leading-[1.6] text-muted">
                {getCurationText(item)}
              </p>
            </div>
          </div>
        </div>
      </div>
    </article>
  );
}
