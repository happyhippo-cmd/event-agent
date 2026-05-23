"""Tour worker — curation helpers.

담당: 취향 기반 관광지 설명 생성 (LLM SNS 카드형 큐레이션)
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from datetime import time as _time

from apps.agents.utils import get_openai_client

CURATION_SYSTEM_PROMPT = """
당신은 한국 관광지 전문 큐레이터입니다.
장소 정보를 바탕으로 SNS 카드형 큐레이션 콘텐츠를 작성하세요.
인스타그램 @daytripkorea 스타일처럼 감성적이고 유익한 문체로 작성합니다.

반드시 아래 형식의 JSON 객체만 반환하세요:
{
  "curations": [
    {
      "id": "장소 ID (입력값 그대로)",
      "headline": "장소의 핵심을 담은 한 줄 제목 (15자 내외)",
      "description": "장소의 역사적·문화적 맥락과 매력을 5문장으로 서술 (300자 내외)",
      "highlights": "핵심 포인트 3가지를 해시태그로 작성 (예: #역사적명소 #야경맛집 #가족나들이)",
      "visit_tip": "방문 시 꼭 알아야 할 팁 또는 추천 포인트 (1문장)",
      "address": "장소 주소 (입력값 그대로, 없으면 빈 문자열)",
      "operate_time": "운영시간 (예: 09:00~18:00, 없으면 빈 문자열)",
      "image": "장소 이미지 URL (입력값 그대로, 없으면 빈 문자열)"
    }
  ]
}

규칙:
- curations 배열에 제공된 장소 목록의 ID를 빠짐없이 포함하세요
- description은 단순 설명이 아닌 스토리텔링 방식으로 작성하세요
- highlights는 실제 overview·카테고리·운영 정보에서 도출하세요 (정보가 없으면 카테고리 기반으로 작성)
- visit_tip은 계절·시간·방문 방법 등 실용적인 내용을 담으세요
- address는 입력된 address 값을 그대로 사용하세요 (없으면 빈 문자열)
- operate_time은 입력된 usetime 값을 그대로 사용하세요 (없으면 빈 문자열)
- image는 입력된 firstimage 값을 그대로 사용하세요 (없으면 빈 문자열)
""".strip()


def curate_tour_items(
    places: list[dict],
    preferences: list[str],
    top_k: int | None = None,
) -> dict[str, dict]:
    """LLM으로 관광지 큐레이션 카드를 생성한다.

    Returns:
        장소 id → 큐레이션 카드 dict (headline·description·highlights·visit_tip·operate_time).
        LLM 미사용/실패 시 빈 dict 반환 — 호출부에서 fallback 처리 필요.
    """
    client = get_openai_client()
    if client is None or not places:
        return {}

    targets = places[:top_k] if top_k else places
    summaries = [
        {
            "id": str(p.get("id", p.get("place_id", ""))),
            "name": p["place_name"],
            "category": p.get("category_name", ""),
            "address": p.get("address", p.get("formatted_address", "")),
            "overview": (p.get("overview") or "")[:300],
            "usetime": p.get("usetime", ""),
            "restdate": p.get("restdate", ""),
            "firstimage": p.get("firstimage", ""),
            "distance_km": p.get("distance_km", ""),
        }
        for p in targets
    ]
    user_content = (
        f"사용자 취향: {preferences}\n\n"
        f"장소 목록:\n{json.dumps(summaries, ensure_ascii=False, indent=2)}"
    )
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": CURATION_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            temperature=0.4,
            response_format={"type": "json_object"},
        )
        raw = json.loads(response.choices[0].message.content)
    except Exception:
        return {}

    items = raw.get("curations", [])
    return {str(item["id"]): item for item in items if "id" in item}


def check_visitability(usetime: str, distance_km: float | None) -> dict:
    """현재 시간 + 도보 이동 시간을 고려해 운영시간 내 방문 가능 여부를 반환.

    usetime이 없거나 파싱 불가 시 빈 dict 반환 (호출부에서 무시).
    도보 속도: 4km/h 기준.
    """
    if not usetime or distance_km is None:
        return {}

    if '상시 개방' in usetime:
        return {"visitability": "available", "visitability_label": "✅ 지금 방문 가능한 장소"}

    walk_minutes = (distance_km / 4.0) * 60
    arrival = datetime.now() + timedelta(minutes=walk_minutes)

    match = re.search(r'(\d{1,2}):(\d{2})\s*[~－\-]\s*(\d{1,2}):(\d{2})', usetime)
    if not match:
        return {}

    open_h, open_m = int(match.group(1)), int(match.group(2))
    close_h, close_m = int(match.group(3)), int(match.group(4))
    if close_h == 24:
        close_h, close_m = 23, 59

    try:
        open_time = _time(open_h, open_m)
        close_time = _time(close_h, close_m)
    except ValueError:
        return {}

    arrival_time = arrival.time()
    if open_time <= close_time:
        is_open = open_time <= arrival_time <= close_time
    else:
        is_open = arrival_time >= open_time or arrival_time <= close_time

    if is_open:
        return {"visitability": "available", "visitability_label": "✅ 지금 방문 가능한 장소"}
    return {"visitability": "unavailable", "visitability_label": "❌ 지금 방문이 어려운 장소"}


def build_card_text(curation: dict) -> str:
    """큐레이션 카드 필드를 정해진 순서로 조합한 설명문을 반환한다."""
    fields = [
        curation.get("headline", ""),
        curation.get("description", ""),
        curation.get("visit_tip", ""),
        curation.get("highlights", ""),
        curation.get("address", ""),
        curation.get("operate_time", ""),
        curation.get("image", ""),
    ]
    return "\n\n".join(f for f in fields if f)


__all__ = ["curate_tour_items", "check_visitability", "build_card_text"]
