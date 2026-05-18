"""Event worker agent backed by the local event DB."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from apps.agents.state import AGENT_EVENT, KDiveState
from apps.agents.utils import get_openai_client

BASE_DIR = Path(__file__).resolve().parents[4]
load_dotenv(BASE_DIR / ".env")

DEFAULT_EVENT_TOP_K = 3
EVENT_DB_PATH = Path(os.getenv("EVENT_DB_PATH", BASE_DIR / "data" / "event_db.sqlite3"))
EVENT_TABLE = os.getenv("EVENT_DB_TABLE", "events_event")

SEOUL_AREAS = (
    "성수", "홍대", "강남", "이태원", "명동", "신촌", "합정", "망원",
    "북촌", "인사동", "압구정", "청담", "한남", "용산", "여의도",
    "종로", "광화문", "동대문", "신사", "가로수길", "잠실", "건대",
    "마포", "연남", "을지로", "익선동", "서촌", "뚝섬", "송파",
)

STOP_WORDS = {
    "팝업", "팝업스토어", "전시", "전시회", "공연", "콘서트", "페스티벌",
    "추천", "해줘", "알려줘", "보여줘", "있어", "어디", "뭐", "좀",
    "이번", "주말", "갈만한", "가볼만한", "열리는", "볼거리", "있을까",
    "있나요", "중에",
}

POPUP_SUBCATEGORIES = {
    "패션": ("패션",),
    "미식": ("식음료", "음식음료"),
    "라이프스타일": ("라이프스타일", "리빙", "홈데코", "홈 인테리어"),
    "캐릭터": ("캐릭터굿즈", "캐릭터"),
    "뷰티": ("뷰티", "향수"),
    "아티스트": ("아티스트", "음악"),
    "스포츠": ("스포츠", "아웃도어"),
    "체험": ("체험", "체험형"),
}

EXHIBITION_SUBCATEGORIES = {
    "아트/회화": ("아트", "회화전"),
    "설치미술": ("설치미술",),
    "사진전": ("사진전", "사진"),
    "미디어아트": ("미디어아트",),
    "체험형": ("체험형전시", "체험전시"),
    "캐릭터": ("캐릭터전시",),
}

CATEGORY_KEYWORDS = {
    "전시": "전시",
    "전시회": "전시",
    "페스티벌": "페스티벌",
    "공연": "공연",
    "콘서트": "공연",
    "박람회": "박람회",
    "팝업스토어": "팝업스토어",
    "팝업": "팝업스토어",
}

SEARCH_FIELDS = (
    "title", "description", "hashtags", "mood_tags", "activity_tags",
    "theme_tags", "space_tags", "audience_tags", "music_genre",
    "new_mood_tags", "new_audience_tags", "new_main_category",
    "new_sub_category", "region", "location",
)


def run_event_agent(
    query: str,
    taste_context: dict[str, Any] | None = None,
    history: list[dict[str, str]] | None = None,
    top_k: int = DEFAULT_EVENT_TOP_K,
) -> dict[str, Any]:
    """Return event recommendations for Surfy's worker-agent pipeline."""

    mood = _event_mood_from_taste(taste_context or {})
    try:
        events = search_events_from_db(query=query, mood=mood, limit=20)
    except Exception as exc:
        return {
            "status": "error",
            "message": f"Event DB 조회 중 오류가 발생했어요: {exc}",
            "recommended_events": [],
        }

    if not events:
        return {
            "status": "no_results",
            "message": "조건에 맞는 이벤트 추천을 찾지 못했어요. 지역이나 이벤트 종류를 조금 더 알려주시면 다시 찾아볼게요.",
            "recommended_events": [],
        }

    curated = curate_events_with_llm(
        events=events,
        query=query,
        taste_context=taste_context or {},
        history=history or [],
        top_k=top_k,
    )
    if not curated:
        curated = [_event_to_card(ev, reason=_fallback_reason(ev, query)) for ev in events[:top_k]]

    names = ", ".join(item["title"] for item in curated[:top_k] if item.get("title"))
    return {
        "status": "ok",
        "message": f"좋아요. 지금 요청에 맞는 이벤트 {len(curated[:top_k])}곳을 골랐어요: {names}",
        "recommended_events": curated[:top_k],
    }


def run_event_agent_for_state(state: KDiveState, top_k: int = DEFAULT_EVENT_TOP_K) -> KDiveState:
    target_agents = state.get("target_agents", [])
    if AGENT_EVENT not in target_agents:
        return state

    result = run_event_agent(
        query=state["user_utterance"],
        taste_context=state.get("taste_context", {}),
        top_k=top_k,
    )
    state["event_result"] = result
    return state


def run(query: str, **kwargs: Any) -> dict[str, Any]:
    return run_event_agent(query=query, **kwargs)


def search_events_from_db(query: str, mood: str = "", limit: int = 20) -> list[dict[str, Any]]:
    rows = _load_event_rows()
    today = date.today().isoformat()
    active_rows = [
        row for row in rows
        if not row.get("end_date") or str(row.get("end_date")) >= today
    ]

    detected_category = _detect_category(query, mood)
    sub_category_filter = _detect_subcategory_filter(query, mood)
    detected_areas = [area for area in SEOUL_AREAS if area in query]
    broad_seoul = "서울" in query and not detected_areas
    keywords = _event_keywords(query, mood, detected_areas)

    filtered = _filter_event_rows(
        active_rows,
        detected_category=detected_category,
        sub_category_filter=sub_category_filter,
        detected_areas=detected_areas,
        broad_seoul=broad_seoul,
    )
    if not filtered and detected_areas:
        filtered = _filter_event_rows(
            active_rows,
            detected_category=detected_category,
            sub_category_filter=sub_category_filter,
            detected_areas=[],
            broad_seoul=broad_seoul,
        )
    if not filtered:
        filtered = active_rows

    scored = [
        (_event_score(row, query, mood, detected_category, sub_category_filter, detected_areas, broad_seoul, keywords), row)
        for row in filtered
    ]
    scored.sort(key=lambda item: (-item[0], str(item[1].get("start_date") or "")))
    return [row for _, row in scored[:limit]]


def _load_event_rows() -> list[dict[str, Any]]:
    if not EVENT_DB_PATH.exists():
        raise FileNotFoundError(f"event DB not found: {EVENT_DB_PATH}")

    conn = sqlite3.connect(EVENT_DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(f"SELECT * FROM {EVENT_TABLE}").fetchall()
    conn.close()
    return [dict(row) for row in rows]


def _filter_event_rows(
    rows: list[dict[str, Any]],
    detected_category: str | None,
    sub_category_filter: list[str],
    detected_areas: list[str],
    broad_seoul: bool,
) -> list[dict[str, Any]]:
    filtered = []
    for row in rows:
        if detected_category and not _row_matches_category(row, detected_category):
            continue
        if sub_category_filter and not _row_matches_subcategory(row, sub_category_filter):
            continue
        if detected_areas and not _row_matches_area(row, detected_areas):
            continue
        if broad_seoul and "서울" not in _row_text(row, ("location", "region")):
            continue
        filtered.append(row)
    return filtered


def _row_matches_category(row: dict[str, Any], category: str) -> bool:
    return category in _row_text(row, ("new_main_category", "main_category", "category"))


def _row_matches_subcategory(row: dict[str, Any], subcategories: list[str]) -> bool:
    haystack = _row_text(row, ("new_sub_category", "sub_category", "detail_category", "description", "hashtags"))
    return any(subcategory and subcategory in haystack for subcategory in subcategories)


def _row_matches_area(row: dict[str, Any], areas: list[str]) -> bool:
    haystack = _row_text(row, ("region", "location"))
    return any(area and area in haystack for area in areas)


def _event_keywords(query: str, mood: str, detected_areas: list[str]) -> list[str]:
    category_keywords = set(CATEGORY_KEYWORDS.keys())
    keywords = []
    for keyword in _extract_keywords(f"{query} {mood}"):
        if keyword in category_keywords or keyword == "서울":
            continue
        if any(area in keyword for area in (*SEOUL_AREAS, *detected_areas)):
            continue
        keywords.append(keyword)
    return list(dict.fromkeys(keywords))


def _event_score(
    row: dict[str, Any],
    query: str,
    mood: str,
    detected_category: str | None,
    sub_category_filter: list[str],
    detected_areas: list[str],
    broad_seoul: bool,
    keywords: list[str],
) -> float:
    score = 0.0
    if detected_category and _row_matches_category(row, detected_category):
        score += 8.0
    if sub_category_filter and _row_matches_subcategory(row, sub_category_filter):
        score += 5.0
    if detected_areas and _row_matches_area(row, detected_areas):
        score += 8.0
    if broad_seoul and "서울" in _row_text(row, ("location",)):
        score += 2.0

    title_text = _row_text(row, ("title",))
    tag_text = _row_text(
        row,
        (
            "hashtags", "mood_tags", "emotion_tags", "activity_tags",
            "theme_tags", "space_tags", "audience_tags", "music_genre",
            "new_mood_tags", "new_audience_tags", "vector_summary", "vector_summary_v2",
        ),
    )
    full_text = _row_text(row, ("title", "description", "location", "region")) + " " + tag_text
    for keyword in keywords:
        if keyword in title_text:
            score += 4.0
        elif keyword in tag_text:
            score += 2.5
        elif keyword in full_text:
            score += 1.0

    if row.get("thumbnail_url"):
        score += 0.4
    if row.get("start_date"):
        score += 0.1
    return score


def _row_text(row: dict[str, Any], keys: tuple[str, ...]) -> str:
    parts = []
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        if isinstance(value, (list, tuple)):
            parts.extend(str(item) for item in value if item)
        else:
            parts.append(str(value))
    return " ".join(parts)


def search_events(
    event_model: Any,
    q_class: Any,
    timezone: Any,
    field_names: set[str],
    query: str,
    mood: str = "",
    limit: int = 20,
) -> list[Any]:
    today = timezone.localdate()
    active_qs = event_model.objects.all()
    if "end_date" in field_names:
        active_qs = active_qs.filter(q_class(end_date__gte=today) | q_class(end_date__isnull=True))

    detected_category = _detect_category(query, mood)
    if detected_category and "new_main_category" in field_names:
        active_qs = active_qs.filter(new_main_category=detected_category)
        if detected_category == "전시" and "commerciality" in field_names:
            active_qs = active_qs.exclude(commerciality="브랜드")

    sub_category_filter = _detect_subcategory_filter(query, mood)
    if sub_category_filter and "new_sub_category" in field_names:
        active_qs = active_qs.filter(new_sub_category__in=sub_category_filter)

    detected_areas = [area for area in SEOUL_AREAS if area in query]
    if "서울" in query and not detected_areas:
        active_qs = _filter_location_contains(active_qs, q_class, field_names, "서울")

    keywords = _extract_keywords(f"{query} {mood}")
    category_keywords = set(CATEGORY_KEYWORDS.keys())
    non_area_keywords = [
        kw for kw in keywords
        if kw not in SEOUL_AREAS and kw not in category_keywords and kw != "서울"
    ]

    loc_filter = _build_or_filter(q_class, field_names, ("location", "region"), detected_areas)
    kw_filter = _build_or_filter(q_class, field_names, SEARCH_FIELDS, non_area_keywords)

    if detected_areas and non_area_keywords and loc_filter and kw_filter:
        qs = active_qs.filter(loc_filter & kw_filter)
        if qs.count() >= 3:
            return list(_order_events(qs, field_names)[:limit])

    if detected_areas and loc_filter:
        qs = active_qs.filter(loc_filter)
        if qs.exists():
            return list(_order_events(qs, field_names)[:limit])

    if non_area_keywords and kw_filter:
        qs = active_qs.filter(kw_filter)
        if qs.exists():
            return list(_order_events(qs, field_names)[:limit])

    if not non_area_keywords and not detected_areas:
        return list(_order_events(active_qs, field_names)[:limit])
    return []


def curate_events_with_llm(
    events: list[Any],
    query: str,
    taste_context: dict[str, Any],
    history: list[dict[str, str]],
    top_k: int,
) -> list[dict[str, Any]]:
    client = get_openai_client()
    if client is None:
        return []

    event_summaries = []
    for idx, event in enumerate(events[:10], 1):
        event_summaries.append(
            {
                "index": idx,
                "title": _event_attr(event, "title"),
                "location": _event_attr(event, "location"),
                "date": _date_range(event),
                "category": _event_attr(event, "new_main_category"),
                "subcategory": _event_attr(event, "new_sub_category"),
                "description": str(_event_attr(event, "description") or "")[:220],
                "hashtags": _listish(_event_attr(event, "hashtags"))[:5],
            }
        )

    recent_history = "\n".join(
        f"{item.get('role')}: {str(item.get('content') or '')[:160]}"
        for item in history[-4:]
    )
    taste_terms = _flatten_terms(
        taste_context,
        ("event_type_keywords", "mood_keywords", "current_mood_keywords", "preferred_music"),
    )
    prompt = (
        f"사용자 질문: {query}\n"
        f"최근 대화:\n{recent_history}\n"
        f"취향 힌트: {', '.join(taste_terms)}\n\n"
        f"후보 이벤트:\n{json.dumps(event_summaries, ensure_ascii=False, indent=2)}\n\n"
        f"후보 중 사용자 질문에 맞는 이벤트를 최대 {top_k}개 고르세요. "
        "추천 이유는 실제 후보 정보에 있는 내용만 사용하세요. "
        "반드시 JSON만 반환하세요: "
        '{"recommendations":[{"index":1,"reason":"2문장 이내 추천 이유"}]}'
    )

    try:
        response = client.chat.completions.create(
            model=os.getenv("EVENT_AGENT_MODEL", "gpt-4o-mini"),
            temperature=0.2,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "너는 K-Dive 서비스의 이벤트 큐레이터입니다. "
                        "서울의 팝업스토어, 전시, 공연, 페스티벌 중 사용자 요청과 맞는 후보만 고릅니다. "
                        "없는 정보는 지어내지 않고 친근한 존댓말로 설명합니다."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content or "{}"
        data = json.loads(raw)
    except Exception:
        return []

    cards = []
    used_indexes = set()
    for rec in data.get("recommendations", []):
        idx = rec.get("index")
        if not isinstance(idx, int) or idx < 1 or idx > len(events) or idx in used_indexes:
            continue
        used_indexes.add(idx)
        cards.append(_event_to_card(events[idx - 1], reason=rec.get("reason") or ""))
        if len(cards) >= top_k:
            break
    return cards


def _load_django_event_model() -> dict[str, Any]:
    try:
        import django
        from django.conf import settings

        settings_module = os.getenv("DJANGO_SETTINGS_MODULE")
        if not settings.configured and not settings_module:
            return {"error": "DJANGO_SETTINGS_MODULE is not configured"}
        if settings_module:
            os.environ.setdefault("DJANGO_SETTINGS_MODULE", settings_module)
        django.setup()

        from django.db.models import Q
        from django.utils import timezone
        from events.models import Event
    except Exception as exc:
        return {"error": str(exc)}
    return {"event_model": Event, "q_class": Q, "timezone": timezone}


def _model_field_names(event_model: Any) -> set[str]:
    return {field.name for field in event_model._meta.get_fields()}


def _detect_category(query: str, mood: str) -> str | None:
    combined = f"{query} {mood}"
    for keyword, category in CATEGORY_KEYWORDS.items():
        if keyword in combined:
            return category
    return None


def _detect_subcategory_filter(query: str, mood: str) -> list[str]:
    combined = f" {query} {mood} "

    def word_match(word: str) -> bool:
        return f" {word} " in combined or combined.startswith(f" {word}") or combined.endswith(f"{word} ")

    is_exhibition = word_match("전시") or word_match("전시회")
    first, second = (
        (EXHIBITION_SUBCATEGORIES, POPUP_SUBCATEGORIES)
        if is_exhibition
        else (POPUP_SUBCATEGORIES, EXHIBITION_SUBCATEGORIES)
    )
    for mapping in (first, second):
        for display_name, db_values in mapping.items():
            normalized = display_name.replace("/", " ")
            if word_match(display_name) or word_match(normalized) or any(word_match(v) for v in db_values):
                return list(db_values)
    return []


def _extract_keywords(text: str) -> list[str]:
    words = [word.strip() for word in text.split() if word.strip()]
    return [word for word in words if len(word) > 1 and not any(stop in word for stop in STOP_WORDS)]


def _build_or_filter(q_class: Any, field_names: set[str], fields: tuple[str, ...], values: list[str]) -> Any | None:
    query = None
    for value in values:
        for field in fields:
            if field not in field_names:
                continue
            condition = q_class(**{f"{field}__icontains": value})
            query = condition if query is None else query | condition
    return query


def _filter_location_contains(qs: Any, q_class: Any, field_names: set[str], value: str) -> Any:
    query = _build_or_filter(q_class, field_names, ("location", "region"), [value])
    return qs.filter(query) if query is not None else qs


def _order_events(qs: Any, field_names: set[str]) -> Any:
    if "start_date" in field_names:
        return qs.order_by("start_date")
    return qs


def _event_mood_from_taste(taste_context: dict[str, Any]) -> str:
    terms = _flatten_terms(
        taste_context,
        ("event_type_keywords", "mood_keywords", "current_mood_keywords", "preferred_music"),
    )
    return " ".join(terms)


def _flatten_terms(data: dict[str, Any], keys: tuple[str, ...]) -> list[str]:
    terms: list[str] = []
    for key in keys:
        value = data.get(key)
        if isinstance(value, list):
            terms.extend(str(item) for item in value if item)
        elif value:
            terms.append(str(value))
    return list(dict.fromkeys(terms))


def _event_to_card(event: Any, reason: str) -> dict[str, Any]:
    title = str(_event_attr(event, "title") or "이벤트")
    category = _event_attr(event, "new_main_category") or _event_attr(event, "category") or "이벤트"
    subcategory = _event_attr(event, "new_sub_category")
    return {
        "id": _event_attr(event, "id") or title,
        "title": title,
        "name": title,
        "location": _event_attr(event, "location") or "",
        "address": _event_attr(event, "location") or "",
        "region": _event_attr(event, "region") or "",
        "category": " · ".join(str(item) for item in (category, subcategory) if item),
        "date": _date_range(event),
        "thumbnail_url": _event_attr(event, "thumbnail_url"),
        "photo_url": _event_attr(event, "thumbnail_url"),
        "photo_urls": [url for url in (_event_attr(event, "thumbnail_url"),) if url],
        "detail_url": _event_attr(event, "detail_url"),
        "store_url": _event_attr(event, "store_url"),
        "description": str(_event_attr(event, "description") or "")[:300],
        "hashtags": _listish(_event_attr(event, "hashtags")),
        "reason": reason,
        "curation": reason or _fallback_reason(event, ""),
    }


def _fallback_reason(event: Any, query: str) -> str:
    title = _event_attr(event, "title") or "이 이벤트"
    location = _event_attr(event, "location")
    category = _event_attr(event, "new_main_category") or "이벤트"
    where = f"{location}에서 열리는 " if location else ""
    query_text = f" '{query}' 요청과 맞는" if query else ""
    return f"{title}은 {where}{category}예요.{query_text} 후보라 일정에 넣어볼 만해요."


def _event_attr(event: Any, key: str) -> Any:
    if isinstance(event, dict):
        return event.get(key)
    return getattr(event, key, None)


def _date_range(event: Any) -> str:
    start = _event_attr(event, "start_date")
    end = _event_attr(event, "end_date")
    if isinstance(start, date):
        start = start.isoformat()
    if isinstance(end, date):
        end = end.isoformat()
    if start and end:
        return f"{start} ~ {end}"
    return str(start or end or "")


def _listish(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item]
    if isinstance(value, tuple):
        return [str(item) for item in value if item]
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(item) for item in parsed if item]
        except json.JSONDecodeError:
            pass
        return [item.strip() for item in text.replace("#", " ").replace(",", " ").split() if item.strip()]
    return []
