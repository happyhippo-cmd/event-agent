from __future__ import annotations

import json
import math
import os
import re
import sqlite3
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from apps.agents.state import AGENT_FOODIE, KDiveState

from .schemas import FoodieAgentResult, FoodieCandidate

BASE_DIR = Path(__file__).resolve().parents[4]
load_dotenv(BASE_DIR / ".env")

DEFAULT_TOP_K = 3
ENRICHED_DB_PATH = Path(os.getenv("ENRICHED_DB_PATH", BASE_DIR / "data" / "foodie_enriched.db"))
CHAIN_BRANDS = (
    "스타벅스", "커피빈", "투썸", "이디야", "메가커피", "컴포즈", "빽다방",
    "할리스", "폴바셋", "파스쿠찌", "엔제리너스", "탐앤탐스", "공차",
    "던킨", "배스킨", "맥도날드", "버거킹", "kfc", "롯데리아", "서브웨이",
    "맘스터치",
)
LOCAL_INTENT_TERMS = ("로컬", "동네", "개인", "독립", "숨은", "체인", "프랜차이즈", "말고")
DISTRICT_PATTERN = re.compile(r"(서울|경기|인천)\s+([가-힣A-Za-z0-9]+(?:구|군|시))")

FOOD_CATEGORY_GROUPS = {
    "카페": ("카페", "커피", "커피전문점", "디저트", "브런치", "베이커리", "북카페", "찻집"),
    "한식": ("한식", "백반", "국밥", "찌개", "고기", "육류"),
    "일식": ("일식", "초밥", "스시", "라멘", "돈까스", "우동", "일본식"),
    "중식": ("중식", "중국", "짜장", "짬뽕", "마라"),
    "양식": ("양식", "파스타", "피자", "이탈리안", "프렌치", "스테이크"),
    "분식": ("분식", "떡볶이", "김밥"),
}
MOOD_KEYWORD_GROUPS = {
    "조용한": ("조용", "차분", "한적", "고요"),
    "감성적인": ("감성", "분위기"),
    "모던한": ("모던", "세련"),
    "활기찬": ("활기", "신나는", "북적"),
}
FOOD_GENRE_KEYWORDS = {
    "한식": ("한식", "국밥", "찌개", "백반"),
    "고기": ("고기", "육류", "구이", "삼겹", "갈비"),
    "해산물": ("해물", "생선", "회", "수산", "낙지"),
    "일식": ("일식", "초밥", "스시", "라멘", "돈까스", "우동"),
    "중식": ("중식", "중국", "짜장", "짬뽕", "마라"),
    "양식": ("양식", "파스타", "피자", "스테이크", "이탈리안"),
    "분식": ("분식", "떡볶이", "김밥"),
    "카페": ("카페", "커피", "커피전문점", "찻집"),
    "디저트": ("디저트", "베이커리", "빵", "아이스크림"),
    "주점": ("술집", "주점", "포장마차", "바"),
}
PRICE_LEVEL_PHRASES = {
    1: "가격 부담이 크지 않아 가볍게 들르기 좋아요.",
    2: "가격대가 무난해서 일상적인 코스로 넣기 좋아요.",
    3: "가격대가 조금 있는 편이라 여유 있게 머물 때 더 잘 맞아요.",
    4: "가격대가 높은 편이라 특별한 날의 선택지로 어울려요.",
}
MENU_KEYS = ("signature_menu", "famous_menu", "recommended_menu", "menu", "menus")


def build_foodie_query(taste_context: dict[str, Any]) -> str:
    """Convert supervisor taste_context into a compact semantic search query."""

    ordered_parts: list[str] = []
    for key in (
        "location_keywords",
        "food_type_keywords",
        "place_type_keywords",
        "mood_keywords",
        "current_mood_keywords",
        "preferred_food",
        "preferred_mood",
        "preferred_music",
        "boosted_keywords",
    ):
        value = taste_context.get(key)
        if isinstance(value, list):
            ordered_parts.extend(str(item) for item in value if item)
        elif value:
            ordered_parts.append(str(value))

    companion = taste_context.get("companion_type")
    active_time = taste_context.get("active_time")
    if companion:
        ordered_parts.append(str(companion))
    if active_time:
        ordered_parts.append(str(active_time))

    deduped = list(dict.fromkeys(ordered_parts))
    return " ".join(deduped).strip() or "서울 분위기 좋은 맛집"


def run_foodie_agent(
    taste_context: dict[str, Any],
    top_k: int = DEFAULT_TOP_K,
) -> dict[str, Any]:
    """Recommend food places from the enriched-place vector DB."""

    query = build_foodie_query(taste_context)
    suppressed = set(taste_context.get("suppressed_keywords") or [])
    location_keywords = list(taste_context.get("location_keywords") or [])
    requested_categories = _requested_categories(taste_context)
    required_moods = _required_moods(taste_context)
    exclude_chains = _wants_non_chain(taste_context)

    try:
        from .vector_store import query_places

        rows = query_places(query=query, top_k=max(top_k * 80, 240) + len(suppressed))
    except Exception as exc:
        result = FoodieAgentResult(
            status="error",
            query=query,
            message=(
                "foodie vector search failed. "
                "Run `python -m apps.agents.workers.foodie.build_vector_db` "
                f"from surfy-backend first. Detail: {exc}"
            ),
        )
        return result.model_dump()

    preferred_rows = [row for row in rows if _matches_location(row, location_keywords)]
    preferred_ids = {row.get("kakao_place_id") for row in preferred_rows}
    fallback_rows = [row for row in rows if row.get("kakao_place_id") not in preferred_ids]
    candidate_rows = preferred_rows + fallback_rows
    candidate_rows = sorted(
        candidate_rows,
        key=lambda row: _row_priority(row, taste_context, requested_categories, location_keywords),
        reverse=True,
    )

    candidates: list[FoodieCandidate] = []
    for row in candidate_rows:
        if _is_unavailable_place(row):
            continue
        if location_keywords and not _matches_location(row, location_keywords):
            continue
        if exclude_chains and _is_chain_place(row):
            continue
        if requested_categories and not _matches_requested_category(row, requested_categories):
            continue
        if required_moods and not _matches_required_moods(row, required_moods):
            continue
        if _matches_suppressed(row, suppressed):
            continue
        candidates.append(_candidate_from_row(row, taste_context))
        if len(candidates) >= top_k:
            break

    status = "ok" if candidates else "no_results"
    message = "" if candidates else "명시 조건에 맞는 enriched place 후보를 찾지 못했습니다."
    return FoodieAgentResult(
        status=status,
        query=query,
        candidates=candidates,
        message=message,
    ).model_dump()


def run_foodie_agent_for_state(state: KDiveState, top_k: int = DEFAULT_TOP_K) -> KDiveState:
    """Run Foodie only when supervisor routed to AGENT_FOODIE."""

    if AGENT_FOODIE not in state.get("target_agents", []):
        return state

    state["foodie_result"] = run_foodie_agent(
        taste_context=state.get("taste_context", {}),
        top_k=top_k,
    )
    return state


def run_nearby_foodie_agent(
    anchors: list[dict[str, Any]],
    taste_context: dict[str, Any],
    top_k: int = DEFAULT_TOP_K,
    radius_km: float = 2.0,
) -> dict[str, Any]:
    """Recommend food places near explicit landmark anchors."""

    valid_anchors = [
        anchor
        for anchor in anchors
        if _none_if_placeholder(anchor.get("lat")) is not None
        and _none_if_placeholder(anchor.get("lng")) is not None
    ]
    query = build_foodie_query(taste_context)
    if not valid_anchors:
        return {
            "status": "no_results",
            "query": query,
            "candidates": [],
            "message": "좌표가 있는 기준 장소를 찾지 못했어요.",
        }

    try:
        rows = _load_food_rows()
    except Exception as exc:
        return {
            "status": "error",
            "query": query,
            "candidates": [],
            "message": f"Foodie DB 조회 중 오류가 발생했어요: {exc}",
        }

    requested_categories = _requested_categories(taste_context)
    required_moods = _required_moods(taste_context)
    suppressed = set(taste_context.get("suppressed_keywords") or [])
    exclude_chains = _wants_non_chain(taste_context)

    ranked_rows = []
    for row in rows:
        if _is_unavailable_place(row):
            continue
        if exclude_chains and _is_chain_place(row):
            continue
        if requested_categories and not _matches_requested_category(row, requested_categories):
            continue
        if required_moods and not _matches_required_moods(row, required_moods):
            continue
        if _matches_suppressed(row, suppressed):
            continue

        nearest = _nearest_anchor(row, valid_anchors)
        if nearest is None or nearest["distance_km"] > radius_km:
            continue

        ranked_rows.append(
            {
                **row,
                "near_place_name": nearest["place"].get("name"),
                "distance_km": nearest["distance_km"],
                "rank_score": _food_rank_score(row, nearest["distance_km"]),
                "similarity_score": 0.0,
            }
        )

    ranked_rows.sort(key=lambda row: row["rank_score"], reverse=True)
    candidates = [_candidate_from_row(row, taste_context) for row in ranked_rows[:top_k]]
    return FoodieAgentResult(
        status="ok" if candidates else "no_results",
        query=query,
        candidates=candidates,
        message="" if candidates else "기준 장소 근처에서 조건에 맞는 맛집을 찾지 못했어요.",
    ).model_dump()


def recommend_nearby_foods_for_places(
    places: list[dict[str, Any]],
    limit: int = 5,
    radius_km: float = 2.0,
) -> dict[str, Any]:
    """Recommend nearby food places for selected onboarding tourist places."""

    anchors = [
        place
        for place in places
        if _none_if_placeholder(place.get("lat")) is not None
        and _none_if_placeholder(place.get("lng")) is not None
    ]
    if not anchors:
        return {"status": "no_results", "foods": [], "message": "좌표가 있는 선택 장소가 없습니다."}

    try:
        rows = _load_food_rows()
    except Exception as exc:
        return {"status": "error", "foods": [], "message": f"Foodie DB 조회 중 오류가 발생했어요: {exc}"}

    ranked_rows = []
    for row in rows:
        if _is_unavailable_place(row) or _is_chain_place(row):
            continue
        nearest = _nearest_anchor(row, anchors)
        if nearest is None or nearest["distance_km"] > radius_km:
            continue
        genre = _food_genre(row.get("category_full") or row.get("category", ""))
        ranked_rows.append(
            {
                **row,
                "genre": genre,
                "near_place_name": nearest["place"].get("name"),
                "distance_km": nearest["distance_km"],
                "rank_score": _food_rank_score(row, nearest["distance_km"]),
            }
        )

    ranked_rows.sort(key=lambda row: row["rank_score"], reverse=True)
    selected = _select_diverse_foods(ranked_rows, limit)
    foods = [_food_payload(row) for row in selected]
    return {
        "status": "ok" if foods else "no_results",
        "foods": foods,
        "message": "" if foods else "조건에 맞는 주변 맛집을 찾지 못했어요.",
    }


def _candidate_from_row(
    row: dict[str, Any],
    taste_context: dict[str, Any],
) -> FoodieCandidate:
    mood_tags = _parse_mood_tags(row.get("mood_tags"))
    preferences = _preference_terms(taste_context)
    matched = _matched_preferences(row, mood_tags, preferences)

    basis_parts = []
    if matched:
        basis_parts.append(f"취향 키워드({', '.join(matched[:3])})와 유사")
    if row.get("near_place_name") and row.get("distance_km") is not None:
        basis_parts.append(f"{row['near_place_name']}에서 약 {row['distance_km']}km")
    if row.get("rating"):
        basis_parts.append(f"평점 {row['rating']}")
    if row.get("review_count"):
        basis_parts.append(f"리뷰 {int(row['review_count']):,}개")
    if row.get("michelin_stars"):
        basis_parts.append(f"미쉐린 {int(row['michelin_stars'])}스타")
    if row.get("is_bib_gourmand"):
        basis_parts.append("빕구르망")

    return FoodieCandidate(
        kakao_place_id=str(row.get("kakao_place_id", "")),
        name=str(row.get("name", "")),
        category=str(row.get("category", "")),
        gu=_display_area(row),
        address=str(row.get("address", "")),
        lat=_none_if_placeholder(row.get("lat")),
        lng=_none_if_placeholder(row.get("lng")),
        rating=_none_if_placeholder(row.get("rating")),
        review_count=int(row.get("review_count") or 0) or None,
        price_level=_none_if_placeholder(row.get("price_level")),
        michelin_stars=int(row.get("michelin_stars") or 0),
        is_bib_gourmand=bool(row.get("is_bib_gourmand")),
        mood_tags=mood_tags,
        similarity_score=float(row.get("similarity_score") or 0.0),
        matched_preferences=matched,
        ranking_basis=" / ".join(basis_parts) or "enriched DB 벡터 유사도 기준",
        curation=_build_curation(row, mood_tags, matched, taste_context),
    )


def _load_food_rows() -> list[dict[str, Any]]:
    if not ENRICHED_DB_PATH.exists():
        raise FileNotFoundError(f"enriched DB not found: {ENRICHED_DB_PATH}")

    conn = sqlite3.connect(ENRICHED_DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT kakao_place_id, name, category_name, gu,
               COALESCE(road_address, address) AS address,
               lat, lng, rating, review_count, price_level,
               COALESCE(mood_tags_naver, mood_tags) AS mood_tags,
               michelin_stars, is_bib_gourmand
        FROM enriched_places
        WHERE lat IS NOT NULL
          AND lng IS NOT NULL
        """
    ).fetchall()
    conn.close()

    result = []
    for row in rows:
        data = dict(row)
        category_name = data.pop("category_name") or ""
        data["category_full"] = category_name
        data["category"] = category_name.split(" > ")[-1]
        result.append(data)
    return result


def _nearest_anchor(row: dict[str, Any], anchors: list[dict[str, Any]]) -> dict[str, Any] | None:
    lat = _none_if_placeholder(row.get("lat"))
    lng = _none_if_placeholder(row.get("lng"))
    if lat is None or lng is None:
        return None

    nearest = None
    for place in anchors:
        distance = _haversine_km(float(lat), float(lng), float(place["lat"]), float(place["lng"]))
        if nearest is None or distance < nearest["distance_km"]:
            nearest = {"place": place, "distance_km": round(distance, 2)}
    return nearest


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlng / 2) ** 2
    )
    return radius * 2 * math.asin(math.sqrt(a))


def _food_genre(category: str) -> str:
    for genre, keywords in FOOD_GENRE_KEYWORDS.items():
        if any(keyword in category for keyword in keywords):
            return genre
    return category.split(">")[-1].strip() or "맛집"


def _food_rank_score(row: dict[str, Any], distance_km: float) -> float:
    rating = float(row.get("rating") or 0)
    review_count = int(row.get("review_count") or 0)
    return rating * 1.2 + min(review_count, 500) / 500 - distance_km * 0.8


def _select_diverse_foods(rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    selected = []
    used_genres: set[str] = set()
    used_names: set[str] = set()

    for row in rows:
        if row["genre"] in used_genres or row.get("name") in used_names:
            continue
        selected.append(row)
        used_genres.add(row["genre"])
        used_names.add(row.get("name"))
        if len(selected) >= limit:
            return selected

    for row in rows:
        if row.get("name") in used_names:
            continue
        selected.append(row)
        used_names.add(row.get("name"))
        if len(selected) >= limit:
            break
    return selected


def _food_payload(row: dict[str, Any]) -> dict[str, Any]:
    genre = row.get("genre") or _food_genre(row.get("category_full") or row.get("category", ""))
    name = row.get("name") or "추천 맛집"
    near_place_name = row.get("near_place_name") or "선택한 장소"
    mood_tags = _parse_mood_tags(row.get("mood_tags"))
    taste_context = {
        "food_type_keywords": [genre],
        "place_type_keywords": [genre],
        "current_keywords": [near_place_name, genre],
    }
    curation = _build_curation(row, mood_tags, [genre], taste_context)
    return {
        "key": f"foodie::{row.get('kakao_place_id') or name}",
        "source_agent": "foodie",
        "id": row.get("kakao_place_id"),
        "name": name,
        "title": name,
        "genre": genre,
        "category": row.get("category") or genre,
        "placeName": near_place_name,
        "address": row.get("address") or "",
        "area": _display_area(row),
        "distance_km": row.get("distance_km"),
        "rating": _none_if_placeholder(row.get("rating")),
        "review_count": int(row.get("review_count") or 0) or None,
        "matched_preferences": [genre],
        "desc": f"{near_place_name} 근처 {genre}",
        "curation": curation,
    }


def _build_curation(
    row: dict[str, Any],
    mood_tags: dict[str, Any],
    matched: list[str],
    taste_context: dict[str, Any],
) -> str:
    place_label = _place_type_label(row)
    atmosphere_phrase = _atmosphere_phrase(mood_tags)
    user_label = _user_label(taste_context)
    topic = _topic_label(place_label)

    if atmosphere_phrase:
        parts = [f"{topic} {atmosphere_phrase} 분위기입니다."]
    else:
        category = str(row.get("category") or place_label).strip()
        parts = [f"{topic} {category} 성격의 장소입니다."]

    parts.append(_fit_sentence(row, taste_context, matched, place_label, user_label))

    if row.get("near_place_name") and row.get("distance_km") is not None:
        parts.append(f"{row['near_place_name']}에서 약 {row['distance_km']}km 거리라 함께 들르기 좋아요.")

    price_phrase = _price_phrase(row, mood_tags)
    if price_phrase:
        parts.append(price_phrase)

    menu_phrase = _menu_phrase(row, mood_tags)
    if menu_phrase:
        parts.append(menu_phrase)

    return " ".join(parts)


def _fit_sentence(
    row: dict[str, Any],
    taste_context: dict[str, Any],
    matched: list[str],
    place_label: str,
    user_label: str,
) -> str:
    category_terms = _taste_terms(taste_context, ("food_type_keywords", "place_type_keywords"))
    mood_terms = _taste_terms(taste_context, ("mood_keywords", "current_mood_keywords", "preferred_mood"))
    mood_phrase = _join_modifiers([_preference_modifier(term) for term in mood_terms[:2]])
    category_phrase = _primary_category_phrase(category_terms, place_label)

    if row.get("near_place_name"):
        return f"선택한 관광지 뒤에 {_genre_experience_phrase(category_phrase, place_label)} 넣고 싶을 때 자연스럽게 이어가기 좋아요."
    if mood_phrase and category_phrase:
        return f"{mood_phrase} {_object_phrase(category_phrase)} 찾는 {user_label}에게 잘 맞을 거예요."
    if mood_phrase:
        return f"{mood_phrase} 분위기를 찾는 {user_label}에게 잘 맞을 거예요."
    if category_phrase:
        return f"{_object_phrase(category_phrase)} 찾는 {user_label}에게 잘 맞을 거예요."
    if matched:
        return f"{_join_unique(matched[:2])} 키워드와 잘 맞는 후보예요."
    return "지금 동선에 가볍게 더하기 좋은 후보예요."


def _primary_category_phrase(category_terms: list[str], place_label: str) -> str:
    if not category_terms and place_label != "장소":
        category_terms = [place_label]
    if "카페" in category_terms:
        category_terms = [term for term in category_terms if term not in ("커피", "커피전문점")]
    return category_terms[0] if category_terms else ""


def _genre_experience_phrase(category: str, place_label: str) -> str:
    label = category or place_label
    if label in ("카페", "커피", "커피전문점"):
        return "카페 휴식을"
    if label == "디저트":
        return "디저트 타임을"
    if label in ("한식", "일식", "중식", "양식", "분식", "고기", "해산물"):
        return f"{label} 한 끼를"
    if label:
        return f"{label} 선택지를"
    return "맛집 코스를"


def _object_phrase(text: str) -> str:
    last = text[-1] if text else ""
    if "가" <= last <= "힣" and (ord(last) - ord("가")) % 28:
        return f"{text}을"
    return f"{text}를"


def _place_type_label(row: dict[str, Any]) -> str:
    category = f"{row.get('category_full') or ''} {row.get('category') or ''}"
    if any(keyword in category for keyword in ("카페", "커피", "찻집", "베이커리", "디저트")):
        return "카페"
    if any(
        keyword in category
        for keyword in (
            "음식점", "한식", "일식", "중식", "양식", "분식", "초밥", "라멘",
            "돈까스", "우동", "파스타", "피자", "고기", "국밥",
        )
    ):
        return "식당"
    if any(keyword in category for keyword in ("술집", "주점", "바")):
        return "공간"
    return "장소"


def _topic_label(label: str) -> str:
    last = label[-1] if label else ""
    if "가" <= last <= "힣" and (ord(last) - ord("가")) % 28:
        return f"이 {label}은"
    return f"이 {label}는"


def _atmosphere_phrase(mood_tags: dict[str, Any]) -> str:
    tags: list[str] = []
    for key in ("atmosphere", "features"):
        value = mood_tags.get(key)
        if isinstance(value, list):
            tags.extend(str(item) for item in value if item)
        elif value:
            tags.append(str(value))

    if not tags:
        for key in ("occasion", "who"):
            value = mood_tags.get(key)
            if isinstance(value, list):
                tags.extend(str(item) for item in value if item)
            elif value:
                tags.append(str(value))

    described = [_describe_mood_tag(tag) for tag in tags]
    return _join_unique(described[:3])


def _describe_mood_tag(tag: str) -> str:
    mapping = {
        "뷰맛집": "뷰가 좋은",
        "로컬맛집": "로컬 느낌이 있는",
        "인스타감성": "감성적인",
        "웨이팅있음": "인기가 많은",
        "예약필수": "인기가 많은",
        "혼자": "혼자 머물기 좋은",
        "친구": "친구와 들르기 좋은",
        "데이트": "데이트하기 좋은",
    }
    return mapping.get(tag, tag)


def _taste_terms(taste_context: dict[str, Any], keys: tuple[str, ...]) -> list[str]:
    terms: list[str] = []
    for key in keys:
        value = taste_context.get(key)
        if isinstance(value, list):
            terms.extend(str(item) for item in value if item)
        elif value:
            terms.append(str(value))
    return list(dict.fromkeys(terms))


def _preference_modifier(term: str) -> str:
    mapping = {
        "로컬 느낌": "로컬 느낌이 있는",
        "로컬": "로컬 느낌이 있는",
        "혼자": "혼자 머물기 좋은",
    }
    return mapping.get(term, term)


def _join_modifiers(items: list[str]) -> str:
    items = [item for item in items if item]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]

    converted = [_to_connective(item) for item in items[:-1]]
    return " ".join([*converted, items[-1]])


def _to_connective(text: str) -> str:
    if text.endswith("한"):
        return f"{text[:-1]}하고"
    if text.endswith("적인"):
        return f"{text[:-2]}이고"
    if text.endswith("있는"):
        return f"{text[:-2]}있고"
    if text.endswith("좋은"):
        return f"{text[:-2]}좋고"
    return f"{text}이고"


def _user_label(taste_context: dict[str, Any]) -> str:
    for key in ("nickname", "user_nickname", "display_name", "name"):
        value = str(taste_context.get(key) or "").strip()
        if value:
            return value if value.endswith("님") else f"{value}님"
    return "사용자님"


def _price_phrase(row: dict[str, Any], mood_tags: dict[str, Any]) -> str:
    price_level = _none_if_placeholder(row.get("price_level"))
    if price_level:
        return PRICE_LEVEL_PHRASES.get(int(price_level), "")

    price_feel = mood_tags.get("price_feel")
    if isinstance(price_feel, list) and price_feel:
        return _price_feel_phrase([str(item) for item in price_feel if item])
    return ""


def _price_feel_phrase(tags: list[str]) -> str:
    phrases = {
        "저렴": "가격 부담이 크지 않아 가볍게 들르기 좋아요.",
        "가성비": "가성비를 중시할 때도 후보로 보기 좋아요.",
        "합리적": "가격대가 무난해서 동선에 넣기 부담이 적어요.",
        "고급": "가격대가 있는 편이라 특별한 식사나 데이트 코스로 더 잘 맞아요.",
    }
    for tag in tags:
        if tag in phrases:
            return phrases[tag]

    descriptors = [_price_feel_descriptor(tag) for tag in tags[:2]]
    if descriptors:
        return f"가격대는 {_join_unique(descriptors)} 쪽에 가까워요."
    return ""


def _price_feel_descriptor(text: str) -> str:
    mapping = {
        "고급": "고급스러운",
        "저렴": "저렴한",
        "합리적": "합리적인",
        "가성비": "가성비가 좋은",
    }
    if text in mapping:
        return mapping[text]
    if text.endswith("적"):
        return f"{text}인"
    if text.endswith("한"):
        return text
    return f"{text}인"


def _menu_phrase(row: dict[str, Any], mood_tags: dict[str, Any]) -> str:
    for key in MENU_KEYS:
        value = row.get(key) or mood_tags.get(key)
        if not value:
            continue
        if isinstance(value, list):
            menus = [str(item) for item in value if item]
        else:
            menus = [str(value)]
        if menus:
            return f"대표 메뉴로는 {_join_unique(menus[:2])}를 먼저 살펴보면 좋아요."
    return ""


def _join_unique(items: list[str]) -> str:
    return ", ".join(dict.fromkeys(item for item in items if item))


def _preference_terms(taste_context: dict[str, Any]) -> list[str]:
    terms: list[str] = []
    for key in (
        "current_keywords",
        "mood_keywords",
        "food_type_keywords",
        "place_type_keywords",
        "preferred_food",
        "preferred_mood",
        "boosted_keywords",
    ):
        value = taste_context.get(key)
        if isinstance(value, list):
            terms.extend(str(item) for item in value if item)
    expanded: list[str] = []
    for term in terms:
        expanded.append(term)
        if "로컬" in term:
            expanded.append("로컬맛집")
        if "카페" in term:
            expanded.extend(["커피", "커피전문점"])
    return list(dict.fromkeys(expanded))


def _all_terms(taste_context: dict[str, Any]) -> list[str]:
    terms: list[str] = []
    for key, value in taste_context.items():
        if isinstance(value, list):
            terms.extend(str(item) for item in value if item)
        elif isinstance(value, str):
            terms.append(value)
    return terms


def _requested_categories(taste_context: dict[str, Any]) -> list[str]:
    terms = _all_terms(taste_context)
    requested: list[str] = []
    for term in terms:
        for category, keywords in FOOD_CATEGORY_GROUPS.items():
            if category in term or any(keyword in term for keyword in keywords):
                requested.append(category)

    # "스타벅스/커피빈 말고" 같은 후속 요청은 카페 맥락으로 해석한다.
    if any(brand in term for term in terms for brand in ("스타벅스", "커피빈", "투썸", "이디야")):
        requested.append("카페")

    # "맛집"은 너무 넓으므로 특정 카테고리가 없을 때만 전체 허용한다.
    return list(dict.fromkeys(category for category in requested if category != "맛집"))


def _matches_requested_category(row: dict[str, Any], requested_categories: list[str]) -> bool:
    haystack = " ".join(
        [
            str(row.get("name", "")),
            str(row.get("category", "")),
            str(row.get("category_full", "")),
            str(row.get("document", "")),
        ]
    )
    for category in requested_categories:
        keywords = FOOD_CATEGORY_GROUPS.get(category, (category,))
        if any(keyword in haystack for keyword in keywords):
            return True
    return False


def _wants_non_chain(taste_context: dict[str, Any]) -> bool:
    terms = _all_terms(taste_context)
    return any(
        marker in term
        for term in terms
        for marker in (*LOCAL_INTENT_TERMS, *CHAIN_BRANDS)
    )


def _is_chain_place(row: dict[str, Any]) -> bool:
    haystack = " ".join(
        [
            str(row.get("name", "")),
            str(row.get("category", "")),
            str(row.get("category_full", "")),
        ]
    ).lower()
    return any(brand.lower() in haystack for brand in CHAIN_BRANDS)


def _required_moods(taste_context: dict[str, Any]) -> list[str]:
    terms: list[str] = []
    for key in ("current_keywords", "mood_keywords", "current_mood_keywords"):
        value = taste_context.get(key)
        if isinstance(value, list):
            terms.extend(str(item) for item in value if item)
        elif value:
            terms.append(str(value))

    required: list[str] = []
    for term in terms:
        for mood, keywords in MOOD_KEYWORD_GROUPS.items():
            if mood in term or any(keyword in term for keyword in keywords):
                required.append(mood)
    return list(dict.fromkeys(required))


def _matches_required_moods(row: dict[str, Any], required_moods: list[str]) -> bool:
    mood_tags = _parse_mood_tags(row.get("mood_tags"))
    haystack = " ".join(
        [
            str(row.get("document", "")),
            json.dumps(mood_tags, ensure_ascii=False),
        ]
    )
    for mood in required_moods:
        keywords = MOOD_KEYWORD_GROUPS.get(mood, (mood,))
        if not any(keyword in haystack for keyword in (mood, *keywords)):
            return False
    return True


def _row_priority(
    row: dict[str, Any],
    taste_context: dict[str, Any],
    requested_categories: list[str],
    location_keywords: list[str],
) -> float:
    score = float(row.get("similarity_score") or 0.0)
    if _matches_location(row, location_keywords):
        score += 0.35
    if requested_categories and _matches_requested_category(row, requested_categories):
        score += 0.3
    mood_tags = _parse_mood_tags(row.get("mood_tags"))
    if "로컬맛집" in json.dumps(mood_tags, ensure_ascii=False):
        score += 0.18
    if _matched_preferences(row, mood_tags, _preference_terms(taste_context)):
        score += 0.15
    if row.get("rating"):
        score += min(float(row["rating"]) / 5.0, 1.0) * 0.04
    if row.get("review_count"):
        score += min(int(row["review_count"]), 500) / 500 * 0.03
    if _is_chain_place(row):
        score -= 0.25
    return score


def _matched_preferences(
    row: dict[str, Any],
    mood_tags: dict[str, Any],
    preferences: list[str],
) -> list[str]:
    haystack = " ".join(
        [
            str(row.get("document", "")),
            str(row.get("name", "")),
            str(row.get("category", "")),
            str(row.get("category_full", "")),
            str(row.get("gu", "")),
            json.dumps(mood_tags, ensure_ascii=False),
        ]
    )
    return [term for term in preferences if term and term in haystack]


def _matches_suppressed(row: dict[str, Any], suppressed: set[str]) -> bool:
    if not suppressed:
        return False
    haystack = " ".join(
        [
            str(row.get("document", "")),
            str(row.get("name", "")),
            str(row.get("category", "")),
            str(row.get("mood_tags", "")),
        ]
    )
    return any(term and term in haystack for term in suppressed)


def _matches_location(row: dict[str, Any], location_keywords: list[str]) -> bool:
    if not location_keywords:
        return False
    haystack = " ".join(
        [
            str(row.get("name", "")),
            _display_area(row),
            str(row.get("address", "")),
        ]
    )
    return any(keyword and keyword in haystack for keyword in location_keywords)


def _is_unavailable_place(row: dict[str, Any]) -> bool:
    haystack = " ".join(
        [
            str(row.get("name", "")),
            str(row.get("address", "")),
            str(row.get("document", "")),
        ]
    )
    return any(term in haystack for term in ("휴업", "폐업", "영업종료"))


def _display_area(row: dict[str, Any]) -> str:
    address = str(row.get("address") or "")
    match = DISTRICT_PATTERN.search(address)
    if match:
        return match.group(2)
    return str(row.get("gu") or "")


def _parse_mood_tags(raw: Any) -> dict[str, Any]:
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        parsed = json.loads(str(raw))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _none_if_placeholder(value: Any) -> Any:
    if value in (None, "", -1, -1.0, 0, 0.0):
        return None
    return value
