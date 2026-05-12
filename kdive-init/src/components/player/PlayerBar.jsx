'use client';

import { useEffect, useState } from 'react';
import { ALBUMS } from '@/data/albums';
import { useKdive } from '@/store/KdiveContext';
import SpotifyControllerPool from './SpotifyControllerPool';

export default function PlayerBar() {
  const { activeAlbum, currentIdx } = useKdive();

  const album = activeAlbum || ALBUMS[currentIdx];
  const [embedAlbum, setEmbedAlbum] = useState(album);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setEmbedAlbum(album);
    }, 250);

    return () => window.clearTimeout(timer);
  }, [album]);

  return (
    <div
      id="sharedPlayerBar"
      className="grid items-center justify-center w-[min(1160px,calc(100%-clamp(48px,6vw,96px)))] p-0 gap-x-[18px] gap-y-3 max-[760px]:w-full max-[760px]:gap-2"
      style={{
        gridTemplateColumns: 'minmax(0,1fr) auto',
        gridTemplateAreas: '"meta meta" "spotify spotify"',
      }}
    >
      <div className="min-w-0 flex items-baseline gap-[14px] max-[760px]:gap-2" style={{ gridArea: 'meta' }}>
        <div className="font-serif text-[20px] leading-[1.08] whitespace-nowrap overflow-hidden text-ellipsis max-[760px]:text-[18px]">
          {album?.title || '–'}
        </div>
        <div className="text-[16px] font-medium text-muted whitespace-nowrap overflow-hidden text-ellipsis max-[760px]:text-[14px]">
          {album?.artist || '–'}
        </div>
      </div>
      <div style={{ gridArea: 'spotify' }}>
        <SpotifyControllerPool album={embedAlbum} />
      </div>
    </div>
  );
}
