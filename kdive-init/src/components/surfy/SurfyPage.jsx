'use client';

import { useKdive } from '@/store/KdiveContext';
import SurfySidebar from './SurfySidebar';
import SurfyChat from './SurfyChat';

export default function SurfyPage() {
  const { loggedIn, activeAppPage, appPhase } = useKdive();
  if (!loggedIn || appPhase !== 'app' || activeAppPage !== 'surfy') return null;

  return (
    <section
      id="surfyPage"
      className="min-h-screen pt-[61px] bg-white"
    >
      <SurfySidebar />
      <main className="min-h-[calc(100vh-61px)] pl-[260px] max-[768px]:pl-[210px] max-[620px]:pl-0">
        <div className="mx-auto w-full max-w-[1060px] px-[clamp(24px,5vw,72px)] max-[768px]:px-4">
          <SurfyChat />
        </div>
      </main>
    </section>
  );
}
