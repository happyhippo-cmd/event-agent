'use client';

import { useState } from 'react';

function getSpotifyUrl(spotifyUri) {
  if (!spotifyUri) return null;
  if (spotifyUri.startsWith('http')) return spotifyUri;
  const [, type, id] = spotifyUri.split(':');
  if (!type || !id) return null;
  return `https://open.spotify.com/${type}/${id}`;
}

export default function AlbumCard({ album, albumIndex, style, isFront, onClick, width }) {
  const [imgError, setImgError] = useState(false);
  const spotifyUrl = getSpotifyUrl(album.spotifyUri);

  if (!style) {
    return null;
  }

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
      <a
        href={spotifyUrl || undefined}
        target="_blank"
        rel="noreferrer"
        onPointerDown={(e) => {
          if (isFront) e.stopPropagation();
        }}
        onClick={(e) => {
          if (isFront) {
            e.stopPropagation();
            return;
          }
          e.preventDefault();
        }}
        aria-label={spotifyUrl ? `${album.title} Spotify에서 열기` : 'Spotify'}
        className={`kd-card-spotify-brand ${spotifyUrl && isFront ? '' : 'pointer-events-none'}`}
      >
        <span className="kd-card-spotify-icon" aria-hidden="true">
          <span />
          <span />
          <span />
        </span>
        <span>Spotify</span>
      </a>
      <div className="kd-card-artwork">
        {!imgError && (
          <img src={album.cover} alt={album.title} onError={() => setImgError(true)} />
        )}
        {imgError && (
          <div className="kd-card-fallback">
            <div className="text-[52px]">♪</div>
            <div className="text-[12px] text-[#555] font-medium">{album.artist}</div>
          </div>
        )}
      </div>
    </div>
  );
}
