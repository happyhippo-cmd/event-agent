'use client';

import { useEffect, useRef } from 'react';
import Script from 'next/script';
import { ALBUMS } from '@/data/albums';
import { useKdive } from '@/store/KdiveContext';

// 원본의 Spotify Iframe API + 컨트롤러 풀 로직을 React로 캡슐화.
// 각 앨범마다 숨겨진 호스트 엘리먼트를 만들어 두고, 활성 앨범이 바뀌면
// 해당 컨트롤러를 play/pause 한다.
export default function SpotifyControllerPool() {
  const apiReadyRef = useRef(false);
  const apiRef = useRef(null);
  const controllersRef = useRef(new Map());
  const hostsRef = useRef(new Map());
  const { activeAlbumId, isPlaying } = useKdive();

  const handleApiReady = (IFrameAPI) => {
    apiRef.current = IFrameAPI;
    apiReadyRef.current = true;
    initControllers();
  };

  // window 콜백 등록
  useEffect(() => {
    if (typeof window === 'undefined') return;
    window.onSpotifyIframeApiReady = handleApiReady;
    // 이미 로드되어 있는 경우
    if (window.SpotifyIframeApi) {
      handleApiReady(window.SpotifyIframeApi);
    }
    return () => {
      // 페이지 이동 시 컨트롤러 정리
      controllersRef.current.forEach((c) => {
        try {
          c.pause();
        } catch (e) {}
      });
    };
  }, []);

  const initControllers = () => {
    if (!apiReadyRef.current || !apiRef.current) return;
    ALBUMS.forEach((album) => {
      const host = hostsRef.current.get(album.id);
      if (!host || controllersRef.current.has(album.id)) return;
      const rect = host.getBoundingClientRect();
      apiRef.current.createController(
        host,
        {
          uri: album.spotifyUri,
          width: Math.round(rect.width) || 300,
          height: Math.round(rect.height) || 80,
        },
        (controller) => {
          controllersRef.current.set(album.id, controller);
        },
      );
    });
  };

  // 활성 앨범의 isPlaying 변화에 따라 컨트롤러 제어
  useEffect(() => {
    const controller = controllersRef.current.get(activeAlbumId);
    if (!controller) return;
    if (isPlaying) {
      try {
        controller.play();
      } catch (e) {}
    } else {
      try {
        controller.pause();
      } catch (e) {}
    }
    // 다른 앨범 컨트롤러들은 모두 정지
    controllersRef.current.forEach((c, id) => {
      if (id !== activeAlbumId) {
        try {
          c.pause();
        } catch (e) {}
      }
    });
  }, [activeAlbumId, isPlaying]);

  return (
    <>
      <Script
        src="https://open.spotify.com/embed/iframe-api/v1"
        strategy="afterInteractive"
      />
      <div className="kd-spotify-pool" id="spotifyControllerPool" aria-hidden="true">
        {ALBUMS.map((album) => (
          <div
            key={album.id}
            ref={(el) => {
              if (el) hostsRef.current.set(album.id, el);
            }}
            className="kd-spotify-host"
            data-album-id={album.id}
            data-spotify-uri={album.spotifyUri}
          />
        ))}
      </div>
    </>
  );
}
