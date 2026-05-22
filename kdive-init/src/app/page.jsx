import Nav from '@/components/nav/Nav';
import TransitionOverlay from '@/components/nav/TransitionOverlay';
import ScrollTopDial from '@/components/nav/ScrollTopDial';
import OnboardingSection from '@/components/onboarding/OnboardingSection';
import CurationSection from '@/components/curation/CurationSection';
import AuthSection from '@/components/auth/AuthSection';
import SurfyPage from '@/components/surfy/SurfyPage';
import HistoryPage from '@/components/history/HistoryPage';
import SplashPage from '@/components/splash/SplashPage';
import MyPage from '@/components/mypage/MyPage';

export default function HomePage() {
  return (
    <>
      <TransitionOverlay />
      <Nav />
      <SplashPage />
      <OnboardingSection />
      <CurationSection />
      <AuthSection />
      <SurfyPage />
      <HistoryPage />
      <MyPage />
      <ScrollTopDial />
    </>
  );
}
