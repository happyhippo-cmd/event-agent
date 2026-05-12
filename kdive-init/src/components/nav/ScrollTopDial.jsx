'use client';

import { useKdive } from '@/store/KdiveContext';

export default function ScrollTopDial() {
  const { loggedIn, goBackToOnboarding } = useKdive();
  if (loggedIn) return null;

  const handleClick = () => {
    goBackToOnboarding();
  };

  return (
    <button
      type="button"
      onClick={handleClick}
      aria-label="최상단으로 이동"
      className="fixed right-[clamp(18px,3vw,34px)] bottom-[clamp(18px,3vw,34px)] z-[110] w-[46px] h-[46px] rounded-full border border-accent-border bg-white text-accent text-[20px] font-semibold leading-none flex items-center justify-center cursor-pointer shadow-[0_10px_28px_rgba(0,0,0,0.1),0_4px_14px_rgba(0,168,232,0.1)] transition-all duration-200 ease hover:-translate-y-[3px] hover:border-accent hover:shadow-[0_14px_34px_rgba(0,0,0,0.13),0_6px_18px_rgba(0,168,232,0.34)] active:translate-y-0 active:scale-[0.96]"
    >
      ↑
    </button>
  );
}
