'use client';

function getSpotifyEmbedUrl(spotifyUri) {
  if (!spotifyUri) return null;
  if (spotifyUri.startsWith('https://open.spotify.com/embed/')) return spotifyUri;
  if (spotifyUri.startsWith('https://open.spotify.com/')) {
    return spotifyUri.replace('https://open.spotify.com/', 'https://open.spotify.com/embed/');
  }
  const [, type, id] = spotifyUri.split(':');
  if (!type || !id) return null;
  return `https://open.spotify.com/embed/${type}/${id}?utm_source=generator`;
}

function getSpotifyOpenUrl(spotifyUri) {
  if (!spotifyUri) return null;
  if (spotifyUri.startsWith('http')) return spotifyUri.replace('/embed/', '/');
  const [, type, id] = spotifyUri.split(':');
  if (!type || !id) return null;
  return `https://open.spotify.com/${type}/${id}`;
}

export function getSpotifyTrackUrl(spotifyUri) {
  return getSpotifyOpenUrl(spotifyUri);
}

// B안: 숨겨진 controller pool 대신 현재 곡의 공식 Spotify Embed를 보이게 렌더한다.
export default function SpotifyControllerPool({ album }) {
  const embedUrl = getSpotifyEmbedUrl(album?.spotifyUri);

  if (!embedUrl) return null;

  return (
    <div className="kd-spotify-embed" id="spotifyEmbed">
      <iframe
        key={album.id}
        title={`${album.title} by ${album.artist} on Spotify`}
        src={embedUrl}
        width="100%"
        height="96"
        allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture"
        loading="eager"
      />
    </div>
  );
}
