'use client';

import { useKdive } from '@/store/KdiveContext';

export default function AuthSection() {
  const { authVisible, loggedIn, loginToSurfy } = useKdive();
  if (loggedIn || !authVisible) return null;

  return (
    <section
      id="authSection"
      className="block min-h-[calc(100vh-61px)] py-[72px] px-[clamp(24px,6vw,72px)] scroll-mt-[70px] bg-white"
    >
      <div className="w-[min(1280px,100%)] min-h-[260px] mx-auto border border-[rgba(0,0,0,0.08)] rounded-[20px] bg-white px-[38px] py-[34px] flex items-center justify-between gap-7 max-[768px]:flex-col max-[768px]:items-start max-[768px]:px-[22px] max-[768px]:py-7 max-[768px]:min-h-[240px]">
        <div className="max-w-[620px]">
          <p className="font-pretendard text-[11px] font-bold tracking-[0.14em] uppercase text-accent mb-[10px]">
            Keep exploring K-Dive
          </p>
          <h2 className="font-serif text-[clamp(1.8rem,3vw,2.5rem)] leading-[1.1] mb-3">
            더 많은 장소를 탐색하고 싶다면?
          </h2>
          <p className="text-[14px] text-muted leading-[1.7]">
            로그인하거나 회원가입하고, 취향에 맞는 음악과 장소 여정을 계속 이어가세요.
          </p>
        </div>
        <div className="flex gap-[10px] flex-wrap justify-end max-[768px]:w-full max-[768px]:justify-stretch">
          <button
            type="button"
            onClick={loginToSurfy}
            className="h-11 px-5 rounded-full border border-[rgba(0,0,0,0.08)] bg-white text-text font-pretendard text-[13px] font-bold cursor-pointer transition-all hover:-translate-y-px hover:shadow-[0_8px_20px_rgba(0,0,0,0.06)] max-[768px]:flex-1"
          >
            로그인
          </button>
          <button
            type="button"
            onClick={loginToSurfy}
            className="h-11 px-5 rounded-full border border-accent bg-accent text-white font-pretendard text-[13px] font-bold cursor-pointer transition-all hover:-translate-y-px hover:shadow-[0_8px_20px_rgba(0,0,0,0.06)] max-[768px]:flex-1"
          >
            회원가입 하기
          </button>
        </div>
      </div>
    </section>
  );
}
