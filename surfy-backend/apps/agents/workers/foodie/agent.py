from __future__ import annotations

import json
from typing import Any

from apps.agents.state import AGENT_FOODIE, KDiveState

from .schemas import FoodieAgentResult, FoodieCandidate

DEFAULT_TOP_K = 5


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

    try:
        from .vector_store import query_places

        rows = query_places(query=query, top_k=top_k + len(suppressed))
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

    candidates: list[FoodieCandidate] = []
    for row in rows:
        if _matches_suppressed(row, suppressed):
            continue
        candidates.append(_candidate_from_row(row, taste_context))
        if len(candidates) >= top_k:
            break

    status = "ok" if candidates else "no_results"
    message = "" if candidates else "조건에 맞는 enriched place 후보를 찾지 못했습니다."
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
        gu=str(row.get("gu", "")),
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
    )


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
    return list(dict.fromkeys(terms))


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
