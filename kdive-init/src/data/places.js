// 샘플 방문 장소 데이터
// category: "tour"(관광지) → ootd/travel 프롬프트로 분기, "food"(맛집) → place 프롬프트로 분기
// 실제 분기는 사진 분석(vision) 결과의 kind 로 자동 결정되며, category 는 표시/필터링용.

/**
 * @typedef {("tour" | "food")} PlaceCategory
 *
 * @typedef {Object} Place
 * @property {string} id
 * @property {string} name
 * @property {string} address
 * @property {PlaceCategory} category
 * @property {string} [photoUrl]      사용자가 업로드한 원본 사진의 data URL (재생성 시 재사용)
 * @property {string} [photoMime]     원본 사진의 mimeType (재생성 시 재사용)
 * @property {string} [generatedUrl]  생성된 결과 이미지
 * @property {string[]} [memos]       오버레이용 손글씨 메모
 * @property {string} [title]         오버레이용 메인 타이틀
 */

/** @type {Place[]} */
export const samplePlaces = [
  {
    id: 'gyeongbokgung',
    name: '경복궁',
    address: '서울특별시 종로구 사직로 161',
    category: 'tour',
  },
  {
    id: 'gwangjang',
    name: '광장시장',
    address: '서울특별시 종로구 창경궁로 88',
    category: 'food',
  },
  {
    id: 'bukchon',
    name: '북촌 한옥마을',
    address: '서울특별시 종로구 계동길 37',
    category: 'tour',
  },
  {
    id: 'ikseondong',
    name: '익선동 골목',
    address: '서울특별시 종로구 익선동',
    category: 'food',
  },
  {
    id: 'namsan',
    name: '남산서울타워',
    address: '서울특별시 용산구 남산공원길 105',
    category: 'tour',
  },
  {
    id: 'mangwon',
    name: '망원시장',
    address: '서울특별시 마포구 포은로8길 14',
    category: 'food',
  },
];
