import Nav from '@/components/nav/Nav';
import TransitionOverlay from '@/components/nav/TransitionOverlay';
import ScrollTopDial from '@/components/nav/ScrollTopDial';
import OnboardingSection from '@/components/onboarding/OnboardingSection';
import CurationSection from '@/components/curation/CurationSection';
import AuthSection from '@/components/auth/AuthSection';
import SurfyPage from '@/components/surfy/SurfyPage';
import HistoryPage from '@/components/history/HistoryPage';

export default function HomePage() {
  return (
    <>
      <TransitionOverlay />
      <Nav />
      <OnboardingSection />
      <CurationSection />
      <AuthSection />
      <SurfyPage />
      <HistoryPage />
      <ScrollTopDial />
    </>
  );
}
