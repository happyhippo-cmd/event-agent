"""Tour worker — filter & rank helpers.

담당: 거리·평점·카테고리 1차 필터 + LLM 기반 최적 장소 선별·재정렬
"""

from __future__ import annotations

import json

from apps.agents.utils import get_openai_client

RANKING_SYSTEM_PROMPT = """
당신은 한국 관광지 추천 전문가입니다.
사용자의 요청과 주변 관광지 목록을 바탕으로, 가장 적합한 장소를 선별하고 순위를 매기세요.

반드시 아래 형식의 JSON만 반환하세요:
{
  "ranked_ids": ["id1", "id2", ...],
  "reason": "선별 기준을 한국어로 간단히 설명"
}

규칙:
- ranked_ids는 제공된 장소 목록의 ID만 사용하세요 (최대 5개)
- 사용자의 선호에 얼마나 잘 맞는지를 기준으로 순서를 정하세요
- 선호 정보가 없으면 카테고리 다양성과 거리를 기준으로 순위를 매기세요
""".strip()

# 카테고리별 기본 점수 (LLM fallback 정렬에 사용)
_CATEGORY_SCORE_MAP = {
    "고궁": 10, "문화유적": 10, "전망대": 8, "테마거리": 7,
    "공원": 6, "시장": 6, "박물관": 5, "미술관": 5,
    "테마파크": 5, "동물원": 4, "수목원": 4,
}


def filter_tour_places(
    candidates: list[dict],
    min_rating: float | None = None,
    category_keywords: list[str] | None = None,
    max_distance_km: float | None = None,
) -> list[dict]:
    """거리·평점·카테고리 기준 1차 필터.

    각 조건은 값이 있을 때만 적용하며, 데이터가 없는 필드는 통과시킨다.
    """
    result = []
    for place in candidates:
        dist = place.get("distance_km")
        if max_distance_km is not None and dist is not None and dist > max_distance_km:
            continue
        rating = place.get("rating")
        if min_rating is not None and rating is not None:
            try:
                if float(rating) < min_rating:
                    continue
            except (TypeError, ValueError):
                pass
        if category_keywords:
            category = place.get("category_name") or ""
            if not any(kw in category for kw in category_keywords):
                continue
        result.append(place)
    return result


def rank_tour_places(
    places: list[dict],
    user_message: str,
    preferences: list[str],
) -> tuple[list[dict], str]:
    """LLM으로 후보 관광지를 선별·재정렬한다.

    LLM 미사용/실패 시 카테고리·취향·거리 점수 기반 정렬로 fallback.

    Returns:
        (재정렬된 장소 리스트, 선별 이유 문자열)
    """
    client = get_openai_client()
    if client is None or not places:
        return _score_and_sort(places, preferences)[:5], "LLM 미사용 — 카테고리·거리 기준 정렬"

    summaries = [
        {
            "id": str(p["id"]),
            "name": p["place_name"],
            "category": p.get("category_name", ""),
            "distance_km": p["distance_km"],
            "overview": (p.get("overview") or "")[:120],
        }
        for p in places
    ]
    user_content = (
        f"User request: {user_message}\n"
        f"Preferences: {preferences}\n\n"
        f"Nearby places:\n{json.dumps(summaries, ensure_ascii=False, indent=2)}"
    )
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": RANKING_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )
        result = json.loads(response.choices[0].message.content)
    except Exception:
        return _score_and_sort(places, preferences)[:5], "LLM 오류 — 카테고리·거리 기준 정렬"

    ranked_ids = result.get("ranked_ids", [])
    reason = result.get("reason", "")
    id_to_place = {str(p["id"]): p for p in places}
    ranked = [id_to_place[rid] for rid in ranked_ids if rid in id_to_place]
    return ranked, reason


def _score_and_sort(places: list[dict], preferences: list[str]) -> list[dict]:
    """LLM fallback: 카테고리 점수 + 취향 매칭 + 거리 기반 정렬."""
    def score(place: dict) -> float:
        category = place.get("category_name") or ""
        dist = place.get("distance_km") or 0.0
        cat_score = next(
            (v for k, v in _CATEGORY_SCORE_MAP.items() if k in category), 0
        )
        pref_score = sum(1 for kw in preferences if kw and kw in category) * 3
        image_bonus = 2 if place.get("firstimage") else 0
        return cat_score + pref_score + image_bonus - float(dist)

    return sorted(places, key=score, reverse=True)


__all__ = ["filter_tour_places", "rank_tour_places"]
