import {
  ALBUMS,
  createFoodSuggestionsForPlace,
  getPlaceKey,
  getPlaceSelectionKey,
  getRecommendedPlaces,
} from '@/data/albums';
import { AREA_HINTS } from '@/data/areaHints';

export function getPlaceSummary(place) {
  const address = place?.address || place?.road_address || place?.address_name;
  if (address) {
    return address.split(' ').slice(0, 3).join(' ');
  }
  const explicitArea = place?.area || place?.gu || place?.district || place?.region || place?.nearby;
  if (explicitArea) return explicitArea;

  const name = place?.name || place?.title || place?.placeName || '';
  return AREA_HINTS.find((hint) => name.includes(hint)) || null;
}

export function getPlaceEmoji(place) {
  if (place?.emoji) return place.emoji;
  const text = `${place?.name || ''} ${place?.category || ''}`.toLowerCase();

  if (text.includes('궁') || text.includes('한옥') || text.includes('temple')) return '🏯';
  if (text.includes('타워') || text.includes('전망') || text.includes('tower')) return '🗼';
  if (text.includes('공원') || text.includes('숲') || text.includes('park')) return '🌿';
  if (text.includes('한강') || text.includes('청계천') || text.includes('호수') || text.includes('river')) return '🌊';
  if (text.includes('시장') || text.includes('market')) return '🥢';
  if (text.includes('거리') || text.includes('골목') || text.includes('street')) return '🚶';
  if (text.includes('전시') || text.includes('미술') || text.includes('museum') || text.includes('gallery')) return '🎨';
  if (text.includes('몰') || text.includes('쇼핑') || text.includes('store')) return '🛍️';
  return '🏛️';
}

export function getFoodEmoji(food) {
  const text = `${food?.title || ''} ${food?.name || ''} ${food?.category || ''} ${food?.genre || ''} ${food?.type || ''}`.toLowerCase();

  if (text.includes('케이크') || text.includes('디저트') || text.includes('베이크') || text.includes('베이커') || text.includes('dessert') || text.includes('cake') || text.includes('bakery')) return '🍰';
  if (text.includes('카페') || text.includes('커피') || text.includes('브런치') || text.includes('cafe') || text.includes('coffee') || text.includes('brunch')) return '☕';
  if (text.includes('분식') || text.includes('떡볶이') || text.includes('김밥') || text.includes('라면')) return '🍢';
  if (text.includes('야식') || text.includes('치킨')) return '🍗';
  if (text.includes('한식') || text.includes('전집') || text.includes('국밥') || text.includes('불고기')) return '🍚';
  return '🍽️';
}

function buildPlaceHistoryItem(key, place, album) {
  const placeSummary = getPlaceSummary(place);

  return {
    key: `place-${key}`,
    rawKey: key,
    type: 'place',
    label: 'Attraction',
    album,
    place,
    title: place.name,
    subtitle: placeSummary || 'Saved attraction',
    emoji: getPlaceEmoji(place),
  };
}

function buildFoodHistoryItem(key, food, album) {
  const foodSummary = food.placeName || getPlaceSummary(food);

  return {
    key: `food-${key}`,
    rawKey: key,
    type: 'food',
    label: 'Restaurant',
    album,
    food,
    title: food.title || food.name || key,
    subtitle: foodSummary || 'Saved restaurant',
    emoji: getFoodEmoji(food),
  };
}

export function buildTrackItems(likedTrackIds) {
  return ALBUMS
    .filter((album) => likedTrackIds.has(album.id))
    .map((album) => ({
      key: `track-${album.id}`,
      type: 'track',
      label: 'Keyword',
      album,
      title: album.vibeEn || album.vibe,
      subtitle: 'K-Dive mood keyword',
      emoji: '♡',
    }));
}

export function buildPlaceItems(likedPlaceKeys, likedPlaceRecords, onboardingPlaces, activeAlbum) {
  const places = [];
  const seen = new Set();
  const pushPlace = (key, place, album) => {
    if (!likedPlaceKeys.has(key) || seen.has(key)) return;
    places.push(buildPlaceHistoryItem(key, likedPlaceRecords[key] || place, album));
    seen.add(key);
  };

  ALBUMS.forEach((album) => {
    getRecommendedPlaces(album).forEach((place) => {
      pushPlace(getPlaceKey(album.id, place.name), place, album);
    });
  });

  onboardingPlaces.forEach((place) => {
    const key = getPlaceSelectionKey(activeAlbum?.id || 'onboarding', place);
    pushPlace(key, place, activeAlbum);
  });

  Object.entries(likedPlaceRecords).forEach(([key, place]) => {
    pushPlace(key, place, activeAlbum);
  });

  likedPlaceKeys.forEach((key) => {
    if (seen.has(key)) return;
    const [, name] = key.split('::');
    pushPlace(key, { name: name || key, category: 'keyword', label: 'Attraction' }, activeAlbum);
  });

  return places;
}

export function buildFoodItems(likedFoodKeys, likedFoodRecords, activeAlbum) {
  const foods = [];
  const seen = new Set();

  ALBUMS.forEach((album) => {
    getRecommendedPlaces(album).forEach((place) => {
      createFoodSuggestionsForPlace(album, place).forEach((food) => {
        if (likedFoodKeys.has(food.key) && !seen.has(food.key)) {
          foods.push(buildFoodHistoryItem(food.key, likedFoodRecords[food.key] || food, album));
          seen.add(food.key);
        }
      });
    });
  });

  Object.entries(likedFoodRecords).forEach(([key, food]) => {
    if (!likedFoodKeys.has(key) || seen.has(key)) return;
    foods.push(buildFoodHistoryItem(key, food, activeAlbum));
    seen.add(key);
  });

  likedFoodKeys.forEach((key) => {
    if (seen.has(key)) return;
    const [, name] = key.split('::');
    foods.push(buildFoodHistoryItem(key, { key, title: name || key, category: 'Restaurant' }, activeAlbum));
    seen.add(key);
  });

  return foods;
}

export function isHistoryItemLiked(item, { likedTrackIds, likedPlaceKeys, likedFoodKeys, pendingUnlikeKeys }) {
  if (pendingUnlikeKeys.has(item.key)) return false;
  if (item.type === 'track') return likedTrackIds.has(item.album?.id);
  if (item.type === 'place') return likedPlaceKeys.has(item.rawKey || item.key.replace(/^place-/, ''));
  if (item.type === 'food') return likedFoodKeys.has(item.rawKey || item.key.replace(/^food-/, ''));
  return true;
}

export function getCurationText(item) {
  if (item.type === 'track') {
    const places = item.album?.places?.map((place) => place.name).join(' · ');
    return `${item.album?.title || item.title}에서 저장한 무드 키워드예요.${places ? ` 이 키워드로 이어지는 추천 장소는 ${places}입니다.` : ''}`;
  }
  if (item.type === 'place') {
    return item.place?.desc || item.place?.curation || `${item.title}와 연결된 attraction curation을 준비하고 있어요.`;
  }
  return item.food?.curation || item.food?.desc || `${item.title}와 연결된 restaurant curation을 준비하고 있어요.`;
}
