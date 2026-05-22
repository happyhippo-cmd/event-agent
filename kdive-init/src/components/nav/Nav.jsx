'use client';

import { useKdive } from '@/store/KdiveContext';

export default function Nav() {
  const { loggedIn, showAuth, activeAppPage, showAppPage } = useKdive();
  const appLinkClass = (page) => (
    `bg-transparent border-0 cursor-pointer transition-colors hover:text-text ${
      activeAppPage === page ? 'text-text font-bold' : 'text-inherit'
    }`
  );

  return (
    <nav className="fixed top-0 left-0 right-0 z-[100] flex items-center justify-between px-12 py-[18px] bg-white/90 backdrop-blur-[14px] border-b border-[rgba(0,0,0,0.08)] max-[760px]:px-[22px] max-[760px]:py-4">
      <div className="font-serif text-[20px] tracking-[-0.02em]">K-Dive</div>
      <div className="flex items-center gap-[clamp(14px,2.2vw,28px)] text-[13px] text-muted whitespace-nowrap max-[760px]:gap-3 max-[760px]:text-[12px]">
        {!loggedIn && (
          <>
            <button type="button" onClick={showAuth} className="bg-transparent border-0 text-inherit cursor-pointer transition-colors hover:text-text">
              Sign up
            </button>
            <button type="button" onClick={showAuth} className="bg-transparent border-0 text-inherit cursor-pointer transition-colors hover:text-text">
              Log in
            </button>
          </>
        )}
        {loggedIn && (
          <>
            <button type="button" data-nav-target="surfy" onClick={() => showAppPage('surfy')} className={appLinkClass('surfy')}>
              Surfy
            </button>
            <button type="button" data-nav-target="history" onClick={() => showAppPage('history')} className={appLinkClass('history')}>
              History
            </button>
            <button type="button" className="bg-transparent border-0 text-inherit cursor-default">
              Log
            </button>
            <button type="button" data-nav-target="mypage" onClick={() => showAppPage('mypage')} className={appLinkClass('mypage')}>
              My page
            </button>
          </>
        )}
      </div>
    </nav>
  );
}
