'use client';

export function HistoryHelp() {
  return (
    <div className="group relative flex h-7 w-7 flex-shrink-0 items-center justify-center">
      <button
        type="button"
        aria-label="History help"
        className="h-6 w-6 rounded-full border border-accent-border bg-transparent text-[11px] font-bold text-accent-dark transition-colors group-hover:border-transparent group-hover:bg-[linear-gradient(135deg,#00a8e8,#006fe8)] group-hover:text-white group-focus-within:border-transparent group-focus-within:bg-[linear-gradient(135deg,#00a8e8,#006fe8)] group-focus-within:text-white"
      >
        ?
      </button>
      <div className="pointer-events-none absolute right-0 top-8 z-20 w-[260px] rounded-[12px] border border-accent-border bg-white px-4 py-3 text-[12px] leading-[1.6] text-black/65 opacity-0 shadow-[0_14px_32px_rgba(0,0,0,0.08)] transition-opacity group-hover:opacity-100 group-focus-within:opacity-100">
        하트를 다시 누르면 History 목록에서 7일 후 사라져요. 체크를 누르면 실제 방문한 장소로 기록되며, 방문 내역은 Log 페이지에서 확인할 수 있어요.
      </div>
    </div>
  );
}

export function FilterIcon() {
  return (
    <span
      aria-hidden="true"
      className="block h-3.5 w-3.5 flex-shrink-0 bg-current [clip-path:polygon(4%_8%,96%_8%,62%_46%,62%_92%,42%_92%,42%_46%)]"
    />
  );
}
