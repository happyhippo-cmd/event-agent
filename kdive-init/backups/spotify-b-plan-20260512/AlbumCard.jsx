'use client';

import { useState } from 'react';
import { useKdive } from '@/store/KdiveContext';

function getSpotifyUrl(spotifyUri) {
  if (!spotifyUri) return null;
  if (spotifyUri.startsWith('http')) return spotifyUri;
  const [, type, id] = spotifyUri.split(':');
  if (!type || !id) return null;
  return `https://open.spotify.com/${type}/${id}`;
}

function SpotifyMark() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      className="w-[12px] h-[12px] flex-shrink-0"
    >
      <circle cx="12" cy="12" r="12" fill="#1DB954" />
      <path
        fill="#fff"
        d="M17.8 16.9c-.2.3-.6.4-.9.2-2.4-1.5-5.4-1.8-9-.98-.34.08-.68-.14-.76-.48-.08-.34.13-.68.47-.76 3.93-.9 7.27-.54 9.95 1.1.3.19.4.59.23.92Zm1.2-2.7c-.23.37-.72.49-1.1.26-2.74-1.68-6.92-2.17-10.16-1.19-.42.13-.86-.11-.98-.53-.13-.42.11-.86.53-.98 3.7-1.12 8.32-.58 11.43 1.33.38.24.5.73.28 1.1Zm.1-2.82C15.8 9.43 10.4 9.25 7.25 10.2c-.5.15-1.02-.13-1.17-.63-.15-.5.13-1.02.63-1.17 3.62-1.1 9.57-.88 13.36 1.37.45.27.6.85.33 1.3-.26.45-.84.6-1.29.32Z"
      />
    </svg>
  );
}

export default function AlbumCard({ album, albumIndex, style, isFront, onClick, width }) {
  const { likedTrackIds, toggleTrackLike } = useKdive();
  const [imgError, setImgError] = useState(false);
  const liked = likedTrackIds.has(album.id);
  const spotifyUrl = getSpotifyUrl(album.spotifyUri);

  if (!style) {
    return null;
  }

  const handleLikeClick = (event) => {
    event.preventDefault();
    event.stopPropagation();
    toggleTrackLike(album.id);
  };

  const handleSpotifyClick = (event) => {
    event.preventDefault();
    event.stopPropagation();
    if (!spotifyUrl) return;
    window.open(spotifyUrl, '_blank', 'noopener,noreferrer');
  };

  return (
    <div
      className={`kd-album-card ${isFront ? 'pos-front' : ''}`}
      style={{
        width: `${width}px`,
        height: `${width * 1.1375}px`,
        transform: `translateX(${style.tx}px) scale(${style.scale})`,
        opacity: style.opacity,
        zIndex: style.zIndex,
        filter: style.filter,
        pointerEvents: 'auto',
      }}
      onClick={onClick}
      title={`${album.title} by ${album.artist}`}
      data-index={albumIndex}
    >
      {!imgError && (
        <>
          <div className="kd-album-cover" style={{ backgroundImage: `url("${album.cover}")` }} />
          <img src={album.cover} alt={album.title} onError={() => setImgError(true)} />
        </>
      )}
      {imgError && (
        <div className="kd-card-fallback">
          <div className="text-[64px]">♪</div>
          <div className="text-[12px] text-[#555] font-medium">{album.artist}</div>
        </div>
      )}
      <button
        type="button"
        onPointerDown={(e) => e.stopPropagation()}
        onClick={handleLikeClick}
        aria-label={`${album.title} ${liked ? '좋아요 취소' : '좋아요'}`}
        aria-pressed={liked}
        className={`absolute top-3 right-3 z-[6] w-[30px] h-[30px] rounded-full border border-white bg-white text-heart text-[18px] leading-none flex items-center justify-center cursor-pointer backdrop-blur-[12px] transition-all ${isFront ? '' : 'opacity-[0.76]'} hover:scale-[1.08]`}
      >
        {liked ? '♥' : '♡'}
      </button>
      <button
        type="button"
        onPointerDown={(e) => e.stopPropagation()}
        onClick={handleSpotifyClick}
        disabled={!spotifyUrl}
        aria-label={`${album.title} Spotify에서 듣기`}
        className="absolute bottom-3 right-3 z-[6] inline-flex items-center gap-[5px] rounded-full border border-white/35 bg-white/90 px-[8px] py-[5px] text-[10px] font-semibold leading-none text-[#1f1f1f] shadow-[0_4px_12px_rgba(0,0,0,0.18)] backdrop-blur-[10px] transition-all hover:bg-white hover:scale-[1.05] disabled:opacity-40"
      >
        <SpotifyMark />
        Spotify
      </button>
      <div className="kd-card-overlay">
        <div className="max-w-[calc(100%-68px)] truncate text-[15px] font-bold text-white leading-[1.3] mb-[3px]">{album.title}</div>
        <div className="max-w-[calc(100%-68px)] truncate text-[12px] text-white/60">{album.artist}</div>
      </div>
    </div>
  );
}
