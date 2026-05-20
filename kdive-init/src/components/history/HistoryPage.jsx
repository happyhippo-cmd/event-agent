'use client';

import { useMemo, useState } from 'react';
import { useKdive } from '@/store/KdiveContext';
import { HistoryCard, EmptyCard, ComingSoonCard } from './HistoryCard';
import MusicKeywordCallout from './MusicKeywordCallout';
import RegionClusterPanel from './RegionClusterPanel';
import SurferGuideCharacter from './SurferGuideCharacter';
import { HistoryHelp, FilterIcon } from './HistoryHelp';
import {
  buildTrackItems,
  buildPlaceItems,
  buildFoodItems,
  isHistoryItemLiked,
} from './historyItems';

const TABS = [
  { id: 'all', label: 'All' },
  { id: 'cluster', label: 'Region Cluster' },
  { id: 'places', label: 'Attractions' },
  { id: 'foods', label: 'Restaurants' },
  { id: 'events', label: 'Exhibitions / Pop-up' },
];

export default function HistoryPage() {
  const {
    loggedIn,
    activeAppPage,
    activeAlbum,
    likedTrackIds,
    likedPlaceKeys,
    likedPlaceRecords,
    likedFoodKeys,
    likedFoodRecords,
    visitedHistoryKeys,
    pendingUnlikeKeys,
    onboardingPlaces,
    toggleHistoryVisit,
    togglePendingUnlike,
    showAppPage,
  } = useKdive();
  const [activeTab, setActiveTab] = useState('all');
  const [expandedCurationKey, setExpandedCurationKey] = useState(null);
  const [sortOrder, setSortOrder] = useState('latest');
  const [mobileTabsOpen, setMobileTabsOpen] = useState(false);

  const tracks = useMemo(
    () => buildTrackItems(likedTrackIds),
    [likedTrackIds]
  );
  const places = useMemo(
    () => buildPlaceItems(likedPlaceKeys, likedPlaceRecords, onboardingPlaces, activeAlbum),
    [likedPlaceKeys, likedPlaceRecords, onboardingPlaces, activeAlbum]
  );
  const foods = useMemo(
    () => buildFoodItems(likedFoodKeys, likedFoodRecords, activeAlbum),
    [likedFoodKeys, likedFoodRecords, activeAlbum]
  );

  if (!loggedIn || activeAppPage !== 'history') return null;

  const allSavedItems = [...places, ...foods];
  const visibleItems = (() => {
    if (activeTab === 'all') return allSavedItems;
    if (activeTab === 'places') return places;
    if (activeTab === 'foods') return foods;
    return [];
  })();

  const isClusterTab = activeTab === 'cluster';
  const isFutureTab = activeTab === 'events';
  const activeTabIndex = Math.max(0, TABS.findIndex((tab) => tab.id === activeTab));
  const activeTabLabel = TABS.find((tab) => tab.id === activeTab)?.label || 'All';
  const sortedItems = sortOrder === 'latest' ? visibleItems : [...visibleItems].reverse();
  const clusterItems = sortOrder === 'latest' ? allSavedItems : [...allSavedItems].reverse();
  const historyEntries = isFutureTab
    ? [
        { kind: 'coming', key: `coming-${activeTab}`, label: TABS.find((tab) => tab.id === activeTab)?.label },
        ...Array.from({ length: 9 }, (_, index) => ({ kind: 'empty', key: `future-empty-${index}`, index })),
      ]
    : sortedItems.map((item) => ({ kind: 'history', key: item.key, item }));

  const handleUnlike = (item) => {
    togglePendingUnlike(item);
  };

  const handleToggleVisited = (item) => {
    if (item.type === 'track') return;
    toggleHistoryVisit(item.key, {
      type: item.type,
      title: item.title,
      subtitle: item.subtitle,
      label: item.label,
      rawKey: item.rawKey,
      emoji: item.emoji,
      albumId: item.album?.id,
      place: item.place,
      food: item.food,
    });
  };

  const handleToggleCuration = (item) => {
    setExpandedCurationKey((current) => (current === item.key ? null : item.key));
  };

  const handleSelectTab = (tabId) => {
    setActiveTab(tabId);
    setMobileTabsOpen(false);
  };

  const handleAskSurfy = () => {
    showAppPage('surfy');
  };

  return (
    <section id="historyPage" className="h-[100dvh] overflow-hidden bg-white max-[760px]:h-auto max-[760px]:min-h-screen max-[760px]:overflow-visible">
      <div className="mx-auto flex h-full w-[min(960px,calc(100%-96px))] flex-col gap-[clamp(12px,1.6vh,20px)] pb-[3vh] pt-[max(84px,8vh)] max-[760px]:h-auto max-[760px]:w-[calc(100%-32px)] max-[760px]:gap-5 max-[760px]:pb-8 max-[760px]:pt-[78px]">
        <header className="flex items-center justify-between gap-5 max-[760px]:flex-col max-[760px]:items-start">
          <div className="min-w-0">
            <h1 className="text-[20px] font-bold uppercase tracking-[0.12em] text-accent">History</h1>
          </div>
        </header>

        <div className="flex items-center gap-2 rounded-[999px] bg-white p-1 max-[760px]:rounded-[22px] max-[760px]:items-start">
          <div className="min-w-0 flex-1">
            <div className="relative grid w-full grid-cols-5 overflow-hidden rounded-[999px] max-[760px]:hidden">
              <span
                aria-hidden="true"
                className="absolute bottom-0 left-0 top-0 rounded-full bg-[linear-gradient(135deg,#00a8e8,#006fe8)] transition-transform duration-200 ease-out"
                style={{
                  width: '20%',
                  transform: `translateX(${activeTabIndex * 100}%)`,
                }}
              />
              {TABS.map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => handleSelectTab(tab.id)}
                  className={`relative z-[1] h-10 rounded-full border-0 px-3 text-[14px] font-bold transition-colors ${
                    activeTab === tab.id ? 'text-white' : 'bg-transparent text-accent-dark hover:text-accent'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>
            <div className="hidden max-[760px]:block">
              <button
                type="button"
                onClick={() => setMobileTabsOpen((open) => !open)}
                aria-expanded={mobileTabsOpen}
                aria-controls="historyMobileTabs"
                className="flex h-10 w-full items-center justify-between rounded-full border-0 bg-white/55 px-4 text-[14px] font-bold text-accent-dark outline-none transition-colors hover:text-accent"
              >
                <span>{activeTabLabel}</span>
                <span className={`text-[12px] transition-transform ${mobileTabsOpen ? 'rotate-180' : ''}`}>⌄</span>
              </button>
              {mobileTabsOpen ? (
                <div
                  id="historyMobileTabs"
                  className="mt-2 grid gap-1 rounded-[18px] border border-[rgba(0,0,0,0.08)] bg-white p-2 shadow-[4px_4px_4px_rgba(0,0,0,0.02)]"
                >
                  {TABS.map((tab) => (
                    <button
                      key={tab.id}
                      type="button"
                      onClick={() => handleSelectTab(tab.id)}
                      className={`flex h-9 items-center justify-between rounded-full border-0 px-3 text-left text-[14px] font-bold transition-colors ${
                        activeTab === tab.id
                          ? 'bg-accent text-white'
                          : 'bg-transparent text-accent-dark hover:bg-accent-soft'
                      }`}
                    >
                      <span>{tab.label}</span>
                      {activeTab === tab.id ? <span aria-hidden="true">✓</span> : null}
                    </button>
                  ))}
                </div>
              ) : null}
            </div>
          </div>
          <button
            type="button"
            onClick={() => setSortOrder((current) => (current === 'latest' ? 'oldest' : 'latest'))}
            className="flex h-10 flex-shrink-0 items-center gap-1.5 rounded-full border-0 bg-transparent px-3 text-[14px] font-bold text-accent-dark transition-colors hover:bg-white/45 hover:text-accent max-[760px]:px-2"
          >
            <FilterIcon />
            {sortOrder === 'latest' ? 'Latest' : 'Oldest'}
          </button>
          <HistoryHelp />
        </div>

        <MusicKeywordCallout tracks={tracks} />

        <div className="kd-history-scroll min-h-0 flex-1 overflow-y-auto pr-3 pt-2 scroll-pt-2 max-[760px]:h-auto max-[760px]:overflow-visible max-[760px]:pr-0">
          {isClusterTab ? (
            <RegionClusterPanel
              items={clusterItems}
              visitedKeys={visitedHistoryKeys}
              expandedCurationKey={expandedCurationKey}
              onToggleCuration={handleToggleCuration}
            />
          ) : (
            <div className="grid grid-cols-1 gap-4 min-[421px]:grid-cols-2 min-[641px]:grid-cols-3 min-[901px]:grid-cols-4 min-[1181px]:grid-cols-5">
              {historyEntries.map((entry) => {
                if (entry.kind === 'coming') {
                  return <ComingSoonCard key={entry.key} label={entry.label} />;
                }
                if (entry.kind === 'empty') {
                  return <EmptyCard key={entry.key} index={entry.index} />;
                }
                const { item } = entry;
                return (
                  <HistoryCard
                    key={item.key}
                    item={item}
                    liked={isHistoryItemLiked(item, { likedTrackIds, likedPlaceKeys, likedFoodKeys, pendingUnlikeKeys })}
                    visited={visitedHistoryKeys.has(item.key)}
                    curationOpen={expandedCurationKey === item.key}
                    onUnlike={handleUnlike}
                    onToggleVisited={handleToggleVisited}
                    onToggleCuration={handleToggleCuration}
                  />
                );
              })}
            </div>
          )}
        </div>
      </div>
      <SurferGuideCharacter onClick={handleAskSurfy} />
    </section>
  );
}
