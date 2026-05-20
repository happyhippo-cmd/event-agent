'use client';

import { getCurationText } from './historyItems';

const MARKER_POSITIONS = [
  'left-[22%] top-[30%]',
  'left-[48%] top-[24%]',
  'left-[68%] top-[38%]',
  'left-[35%] top-[58%]',
  'left-[58%] top-[66%]',
  'left-[76%] top-[20%]',
  'left-[18%] top-[70%]',
  'left-[44%] top-[44%]',
];

export default function RegionClusterPanel({ items, visitedKeys, expandedCurationKey, onToggleCuration }) {
  const markerItems = items.slice(0, MARKER_POSITIONS.length);

  return (
    <section className="grid h-full min-h-0 grid-cols-[minmax(0,1.2fr)_minmax(280px,0.8fr)] gap-4 max-[760px]:h-auto max-[760px]:grid-cols-1">
      <div className="relative h-full min-h-0 overflow-hidden rounded-[20px] border border-[rgba(0,0,0,0.08)] bg-[#f6fbfe] shadow-[4px_4px_4px_rgba(0,0,0,0.02)] max-[760px]:h-[320px]">
        <div className="absolute inset-4 rounded-[18px] border border-accent-border bg-white/70">
          <div className="absolute inset-0 opacity-[0.28] [background-image:linear-gradient(rgba(0,168,232,0.18)_1px,transparent_1px),linear-gradient(90deg,rgba(0,168,232,0.18)_1px,transparent_1px)] [background-size:48px_48px]" />
          {markerItems.map((item, index) => (
            <div
              key={`cluster-marker-${item.key}`}
              className={`absolute ${MARKER_POSITIONS[index]} flex h-8 w-8 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full bg-accent text-[12px] font-bold text-white shadow-[0_4px_12px_rgba(0,168,232,0.22)]`}
              title={item.title}
            >
              {index + 1}
            </div>
          ))}
        </div>
      </div>

      <div className="kd-history-scroll flex h-full min-h-0 flex-col gap-3 overflow-y-auto pr-2 max-[760px]:h-[420px]">
        {items.length ? items.map((item, index) => {
          const curationOpen = expandedCurationKey === item.key;

          return (
            <article
              key={`cluster-${item.key}`}
              className={`rounded-[14px] border bg-white px-4 py-3 shadow-[4px_4px_4px_rgba(0,0,0,0.02)] transition-colors ${
                curationOpen ? 'border-accent-border' : 'border-[rgba(0,0,0,0.08)]'
              }`}
            >
              <div className="grid grid-cols-[24px_minmax(0,1fr)_24px] items-start gap-x-3 gap-y-3">
                <span className="flex h-6 w-6 flex-shrink-0 items-center justify-center text-[18px] leading-none opacity-80">
                  {item.emoji}
                </span>
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-[12px] font-bold uppercase tracking-[0.12em] text-accent">{index + 1}</span>
                    <span className="truncate text-[12px] font-bold uppercase tracking-[0.12em] text-accent">{item.label}</span>
                  </div>
                  <h3 className="mt-1 truncate text-[16px] font-bold text-text">{item.title}</h3>
                  <p className="mt-1 flex min-w-0 items-center text-[14px] text-muted">
                    <span className="truncate">{item.subtitle}</span>
                  </p>
                </div>
                {visitedKeys.has(item.key) ? (
                  <span className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-[#2d8c5d] text-[16px] font-bold leading-none text-white">
                    <span className="block translate-y-[2px]">✓</span>
                  </span>
                ) : null}

                <button
                  type="button"
                  onClick={() => onToggleCuration(item)}
                  aria-expanded={curationOpen}
                  className="col-span-2 col-start-2 mt-1 flex w-full cursor-pointer items-center justify-between border-0 bg-transparent text-left text-[14px] font-medium text-muted focus:outline-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
                >
                  <span className="tracking-[0.08em]">Curation</span>
                  <span className={`flex h-5 w-5 items-center justify-center transition-transform ${curationOpen ? 'rotate-180 text-accent-border' : 'text-muted'}`}>⌄</span>
                </button>

                <div className={`kd-history-curation col-span-2 col-start-2 ${curationOpen ? 'is-open' : ''}`} aria-hidden={!curationOpen}>
                  <div>
                    <p className="mt-2 border-t border-[rgba(0,0,0,0.08)] pt-3 text-[14px] leading-[1.6] text-muted">
                      {getCurationText(item)}
                    </p>
                  </div>
                </div>
              </div>
            </article>
          );
        }) : (
          <div className="rounded-[14px] border border-[rgba(0,0,0,0.08)] bg-white px-5 py-4 text-[13px] text-muted shadow-[4px_4px_4px_rgba(0,0,0,0.02)]">
            Saved places will appear here.
          </div>
        )}
      </div>
    </section>
  );
}
