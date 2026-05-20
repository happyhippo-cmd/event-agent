// /api/history-items/ POST 요청 페이로드를 빌드하는 공용 함수.
// KdiveContext의 like 토글 흐름과 HistoryPage의 unlike 취소(=복구) 흐름이 같은 스키마를 따른다.

export function buildTrackPayload(album, { source = 'curation' } = {}) {
  return {
    item_key: `track-${album.id}`,
    item_type: 'music_keyword',
    title: album.vibe,
    category: 'music_keyword',
    liked_source: source,
    payload: {
      album_id: album.id,
      title: album.title,
      artist: album.artist,
      vibe: album.vibe,
      spotify_uri: album.spotifyUri,
    },
  };
}

export function buildPlacePayload({ itemKey, albumId, placeName, placeRecord }, { source = 'curation' } = {}) {
  const payload = placeRecord || { name: placeName };
  return {
    item_key: itemKey,
    item_type: 'attraction',
    title: payload.name || placeName,
    category: payload.category || 'attraction',
    liked_source: source,
    place_key: itemKey,
    payload: {
      album_id: albumId,
      ...payload,
    },
  };
}

export function buildFoodPayload({ itemKey, foodKey, foodRecord }, { source = 'curation' } = {}) {
  const payload = foodRecord || { key: foodKey };
  return {
    item_key: itemKey,
    item_type: 'restaurant',
    title: payload.title || payload.name || foodKey,
    category: payload.category || payload.genre || payload.type || 'restaurant',
    liked_source: source,
    place_key: itemKey,
    payload,
  };
}

// History 카드에서 unlike 예약을 취소(복구)할 때 사용.
// HistoryCard item.type 기준으로 분기.
export function buildRestorePayloadFromHistoryItem(item) {
  if (item.type === 'track') {
    return buildTrackPayload(
      {
        id: item.album?.id,
        title: item.album?.title,
        artist: item.album?.artist,
        vibe: item.album?.vibe || item.title,
        spotifyUri: item.album?.spotifyUri,
      },
      { source: 'history' }
    );
  }

  if (item.type === 'place') {
    return buildPlacePayload(
      {
        itemKey: item.key,
        albumId: item.album?.id,
        placeName: item.title,
        placeRecord: item.place,
      },
      { source: 'history' }
    );
  }

  return buildFoodPayload(
    {
      itemKey: item.key,
      foodKey: item.rawKey || item.key,
      foodRecord: item.food,
    },
    { source: 'history' }
  );
}
