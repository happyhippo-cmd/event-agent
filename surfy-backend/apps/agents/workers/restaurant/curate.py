"""Restaurant curation helpers."""

from __future__ import annotations

import json
import os
from typing import Any

from apps.agents.utils import get_openai_client


def curate_restaurant_items(
    items: list[Any],
    taste_context: dict[str, Any],
    query: str,
    top_k: int,
) -> dict[str, str]:
    """Generate LLM curations keyed by each item's stable id.

    Returns an empty dict when OpenAI is not configured or the call fails, so
    callers can keep their deterministic fallback curation.
    """

    client = get_openai_client()
    if client is None or not items:
        return {}

    item_summaries = []
    item_by_id = {}
    for item in items[:top_k]:
        payload = _item_payload(item)
        item_id = _item_id(payload)
        if not item_id:
            continue
        item_by_id[item_id] = payload
        item_summaries.append(
            {
                "id": item_id,
                "name": payload.get("name") or payload.get("title"),
                "category": payload.get("category") or payload.get("genre"),
                "area": payload.get("gu") or payload.get("area"),
                "address": payload.get("address"),
                "distance_km": payload.get("distance_km"),
                "rating": payload.get("rating"),
                "review_count": payload.get("review_count"),
                "price_level": payload.get("price_level"),
                "mood_tags": payload.get("mood_tags") or {},
                "matched_preferences": payload.get("matched_preferences") or [],
                "ranking_basis": payload.get("ranking_basis") or "",
            }
        )

    if not item_summaries:
        return {}

    prompt = (
        f"사용자 요청/검색어: {query}\n"
        f"사용자 취향 컨텍스트: {json.dumps(_compact_taste_context(taste_context), ensure_ascii=False)}\n\n"
        f"추천 후보:\n{json.dumps(item_summaries, ensure_ascii=False, indent=2)}\n\n"
        "각 후보의 curation을 한국어 존댓말 1~2문장으로 작성하세요.\n"
        "- 장소명, 카테고리, 분위기 태그, 거리, 평점, 리뷰 수처럼 제공된 정보만 사용하세요.\n"
        "- 메뉴 정보가 없으면 메뉴를 지어내지 마세요.\n"
        "- 가격 정보가 price_level 또는 mood_tags.price_feel에 있을 때만 자연스럽게 언급하세요.\n"
        "- '가격 감각', '양식 취향을 가진'처럼 어색한 표현은 쓰지 마세요.\n"
        "- 사용자 닉네임이 있으면 한 번만 자연스럽게 사용하세요.\n"
        "반드시 JSON만 반환하세요: "
        '{"curations":[{"id":"후보 id","curation":"큐레이션 문장"}]}'
    )

    try:
        response = client.chat.completions.create(
            model=os.getenv("RESTAURANT_CURATION_MODEL") or os.getenv("FOODIE_CURATION_MODEL", "gpt-4o-mini"),
            temperature=0.35,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "너는 K-Dive의 맛집 큐레이터입니다. "
                        "추천 후보의 실제 데이터만 바탕으로 자연스럽고 짧은 큐레이션을 씁니다. "
                        "없는 메뉴, 가격, 분위기는 절대 지어내지 않습니다."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
        )
        data = json.loads(response.choices[0].message.content or "{}")
    except Exception:
        return {}

    curations: dict[str, str] = {}
    for item in data.get("curations", []):
        item_id = str(item.get("id") or "").strip()
        curation = str(item.get("curation") or "").strip()
        if item_id in item_by_id and curation:
            curations[item_id] = curation
    return curations


def _item_payload(item: Any) -> dict[str, Any]:
    if isinstance(item, dict):
        return item
    if hasattr(item, "model_dump"):
        return item.model_dump()
    return dict(item)


def _item_id(item: dict[str, Any]) -> str:
    return str(
        item.get("kakao_place_id")
        or item.get("id")
        or item.get("key")
        or item.get("name")
        or item.get("title")
        or ""
    ).strip()


def _compact_taste_context(taste_context: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "nickname",
        "location_keywords",
        "food_type_keywords",
        "place_type_keywords",
        "mood_keywords",
        "current_mood_keywords",
        "preferred_mood",
        "suppressed_keywords",
        "companion_type",
        "active_time",
    )
    return {key: taste_context.get(key) for key in keys if taste_context.get(key)}


__all__ = ["curate_restaurant_items"]
