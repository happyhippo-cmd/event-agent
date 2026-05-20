"""Event worker agent backed by the local event DB."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import date
from itertools import zip_longest
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
    "근처", "주변", "쪽", "근방", "인근", "지역", "동네",
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
    # 페스티벌 & 약어
    "페스티벌": "페스티벌",
    "페스타": "페스티벌",
    "락페": "페스티벌",
    "락 페스티벌": "페스티벌",
    "재페": "페스티벌",
    "재즈 페스티벌": "페스티벌",
    "뮤직페스티벌": "페스티벌",
    "뮤직 페스티벌": "페스티벌",
    "뮤페": "페스티벌",
    "EDM 페스티벌": "페스티벌",
    "festival": "페스티벌",
    "FESTIVAL": "페스티벌",
    # 공연 & 약어
    "공연": "공연",
    "콘서트": "공연",
    "내한공연": "공연",
    "내한": "공연",
    "팬미팅": "공연",
    "팬콘": "공연",
    # 기타
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

# 힙하고 활동적인 이벤트를 우선 노출하기 위한 mood 가중치
HIP_MOOD_TAGS = {"힙한", "트렌디한", "감각적인", "유니크한", "SNS감성", "활동적인", "이색적인", "핫플"}

# 쿼리의 장르 키워드를 DB의 music_genre 값으로 매핑한다.
# music_genre는 JSON 배열(예: '["K-pop 아이돌"]')로 저장되어 있다.
# 사용자가 "아이돌"이라 했는데 닐로(인디)·버둥(인디)이 추천되는 회귀를 막기 위해
# retrieval 결과를 LLM에 넘기기 전에 하드 필터로 거른다.
GENRE_KEYWORDS = {
    "아이돌": ("K-pop 아이돌",),
    "K-pop": ("K-pop 아이돌",),
    "k-pop": ("K-pop 아이돌",),
    "kpop": ("K-pop 아이돌",),
    "케이팝": ("K-pop 아이돌",),
    "인디": ("인디",),
    "재즈": ("재즈",),
    "힙합": ("랩/힙합",),
    "랩": ("랩/힙합",),
    "락": ("록", "록/밴드"),
    "록": ("록", "록/밴드"),
    "밴드": ("록/밴드",),
    "EDM": ("EDM",),
    "edm": ("EDM",),
    "트로트": ("트로트",),
    "J-pop": ("J-pop",),
    "j-pop": ("J-pop",),
    "제이팝": ("J-pop",),
    "내한": ("해외 아티스트",),
    "해외": ("해외 아티스트",),
}


def _retrieve_and_hard_filter(
    query: str,
    mood: str,
    location_keywords: list[str],
    genre_filter: list[str],
) -> list[dict[str, Any]]:
    """Keyword+vector 검색 후 location/genre 하드 필터를 적용한 후보 풀을 반환."""
    events = search_events_from_db(query=query, mood=mood, limit=20)
    events = _merge_with_vector_search(events, query=query, mood=mood, limit=20)
    if location_keywords:
        events = _filter_by_explicit_location(events, location_keywords)
    if genre_filter:
        events = _filter_by_genre(events, genre_filter)
    return events


def run_event_agent(
    query: str,
    taste_context: dict[str, Any] | None = None,
    history: list[dict[str, str]] | None = None,
    top_k: int = DEFAULT_EVENT_TOP_K,
) -> dict[str, Any]:
    """Return event recommendations for Surfy's worker-agent pipeline."""

    mood = _event_mood_from_taste(taste_context or {})
    location_keywords = [
        str(loc) for loc in (taste_context or {}).get("location_keywords") or [] if loc
    ]
    genre_filter = _detect_genre_filter(query, mood)

    try:
        events = _retrieve_and_hard_filter(query, mood, location_keywords, genre_filter)
    except Exception as exc:
        return {
            "status": "error",
            "message": f"Event DB 조회 중 오류가 발생했어요: {exc}",
            "recommended_events": [],
        }

    # Function calling: 하드 필터로 후보가 0건이면 LLM이 어떤 제약을 완화할지 결정.
    # tool_calls API로 진짜 도구 호출 한 번 수행 — 무한 루프 방지 위해 retry는 1회.
    relax_note = ""
    # 완화가 일어났을 때 curate 단계로 넘길 taste_context도 같이 풀어야 한다.
    # 그렇지 않으면 curate 프롬프트의 0순위 룰("지역명이 명시된 경우 해당 지역만 선정")이
    # 다른 지역 후보를 모두 거부해서 결과가 다시 비게 된다.
    curate_taste_context = taste_context or {}
    if not events and (location_keywords or genre_filter):
        relaxation = _ask_llm_for_relaxation(
            query=query, location_keywords=location_keywords, genre_filter=genre_filter,
        )
        if relaxation:
            relaxed_loc = [] if relaxation.get("relax_location") else location_keywords
            relaxed_genre = [] if relaxation.get("relax_genre") else genre_filter
            if relaxed_loc != location_keywords or relaxed_genre != genre_filter:
                try:
                    events = _retrieve_and_hard_filter(query, mood, relaxed_loc, relaxed_genre)
                except Exception:
                    events = []
                if events:
                    relax_note = relaxation.get("note") or ""
                    curate_taste_context = dict(taste_context or {})
                    if relaxation.get("relax_location"):
                        curate_taste_context["location_keywords"] = []

    if not events:
        return {
            "status": "no_results",
            "message": "조건에 맞는 이벤트 추천을 찾지 못했어요. 지역이나 이벤트 종류를 조금 더 알려주시면 다시 찾아볼게요.",
            "recommended_events": [],
        }

    curated = curate_events_with_llm(
        events=events,
        query=query,
        taste_context=curate_taste_context,
        history=history or [],
        top_k=top_k,
    )

    # curated가 None이면 LLM 호출 자체가 실패한 것 → 폴백
    if curated is None:
        curated = [_event_to_card(ev, reason=_fallback_reason(ev, query)) for ev in events[:top_k]]
    # curated가 빈 배열이면 LLM이 의도적으로 비움 (맞는 후보 없음)
    elif not curated:
        return {
            "status": "no_results",
            "message": "요청하신 조건에 딱 맞는 이벤트를 찾지 못했어요. 다른 장르나 키워드로 다시 알려주시면 더 잘 찾아드릴게요.",
            "recommended_events": [],
        }

    names = ", ".join(item["title"] for item in curated[:top_k] if item.get("title"))
    base_msg = f"좋아요. 지금 요청에 맞는 이벤트 {len(curated[:top_k])}곳을 골랐어요: {names}"
    final_msg = f"{relax_note} {base_msg}".strip() if relax_note else base_msg
    return {
        "status": "ok",
        "message": final_msg,
        # 호출 측(dummy_server 등)이 최종 응답에 prepend할 수 있도록 별도 필드로도 노출.
        "relaxation_note": relax_note,
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


def _filter_by_explicit_location(
    rows: list[dict[str, Any]], location_keywords: list[str]
) -> list[dict[str, Any]]:
    """사용자가 명시한 지역(location_keywords)에 해당하는 후보만 남긴다.

    벡터 검색은 location 필터를 지원하지 않아서 merge 단계에서 다른 지역
    이벤트가 섞여 들어온다. LLM 프롬프트의 0순위 룰만으로는 비결정적이라
    하드 필터로 LLM이 위반 자체를 못 하게 한다. location/region/address에
    부분 문자열 매칭한다.
    """
    if not location_keywords:
        return rows
    return [
        row for row in rows
        if any(
            area and area in _row_text(row, ("location", "region", "address"))
            for area in location_keywords
        )
    ]


def _detect_genre_filter(query: str, mood: str) -> list[str]:
    """쿼리·mood에서 음악 장르 키워드를 잡아 DB music_genre 값 목록으로 변환."""
    combined = f"{query} {mood}"
    detected: list[str] = []
    for keyword, db_values in GENRE_KEYWORDS.items():
        if keyword in combined:
            for value in db_values:
                if value not in detected:
                    detected.append(value)
    return detected


def _filter_by_genre(
    rows: list[dict[str, Any]], genre_filter: list[str]
) -> list[dict[str, Any]]:
    """music_genre가 요청 장르와 명시적으로 일치하는 후보만 남긴다 (strict).

    music_genre는 JSON 배열 문자열(예: '["K-pop 아이돌"]')로 저장. "기타"·"모름"·
    빈 배열은 분류 정보가 없어 요청 장르 매칭이 불가하므로 제외한다.
    이렇게 해야 결과가 0건일 때 function calling 완화 경로가 정확히 트리거된다.

    예: 사용자 "아이돌 콘서트" → genre_filter=["K-pop 아이돌"]
        - 닐로(["인디"]) → 제거
        - I.O.I(["K-pop 아이돌"]) → 유지
        - 분류 없는 콘서트(["기타"]) → 제거 (트로트인지 발라드인지 알 수 없음)
    """
    if not genre_filter:
        return rows
    filtered: list[dict[str, Any]] = []
    for row in rows:
        raw = row.get("music_genre") or ""
        try:
            tags = json.loads(raw) if isinstance(raw, str) and raw.startswith("[") else (raw if isinstance(raw, list) else [raw])
        except (json.JSONDecodeError, TypeError):
            tags = [raw] if raw else []
        tags = [str(t) for t in tags if t]
        if any(g in tags for g in genre_filter):
            filtered.append(row)
    return filtered


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

    # 이미지 있는 이벤트 강하게 우선 (없으면 UI가 깨짐)
    if row.get("thumbnail_url"):
        score += 4.0
    if row.get("start_date"):
        score += 0.1

    # 힙한/트렌디한 mood 태그 보너스
    mood_text = _row_text(row, ("new_mood_tags", "mood_tags"))
    hip_count = sum(1 for tag in HIP_MOOD_TAGS if tag in mood_text)
    score += hip_count * 1.5

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


_RELAX_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "search_events_relaxed",
        "description": (
            "사용자 요청 조건이 너무 좁아 후보가 0건일 때, 어떤 제약을 완화해서 "
            "다시 검색할지 결정한다. 지역과 장르 중 더 우선해야 할 것을 유지하고 "
            "덜 본질적인 쪽을 풀어라. 예: 사용자가 특정 장르(아이돌·재즈 등)와 "
            "지역(성수·홍대 등)을 둘 다 말했다면, 장르가 보통 더 핵심이라 location을 "
            "푸는 게 합리적이다. 단순 '근처' 같은 약한 지역 표현은 더 적극적으로 푼다."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "relax_location": {
                    "type": "boolean",
                    "description": "true면 location_keywords를 무시하고 전체 지역에서 재검색.",
                },
                "relax_genre": {
                    "type": "boolean",
                    "description": "true면 music_genre 하드 필터를 끄고 재검색.",
                },
                "note": {
                    "type": "string",
                    "description": (
                        "사용자에게 보여줄 한 문장 한국어 안내. 어떤 조건을 풀었는지·왜 그랬는지 "
                        "친근한 존댓말로. 예: '성수에 트로트 공연은 없어서 서울 다른 지역도 함께 봤어요.'"
                    ),
                },
            },
            "required": ["relax_location", "relax_genre", "note"],
        },
    },
}


def _ask_llm_for_relaxation(
    query: str,
    location_keywords: list[str],
    genre_filter: list[str],
) -> dict[str, Any] | None:
    """0건 결과일 때 LLM이 어떤 하드 필터를 풀지 tool_call로 결정한다.

    OpenAI function calling으로 _RELAX_TOOL_SCHEMA를 호출시키고 그 인자를 반환.
    툴 호출이 안 일어나거나 파싱 실패면 None — 호출부에서 그대로 no_results 처리.
    """
    client = get_openai_client()
    if client is None:
        return None
    system_msg = (
        "너는 사용자 요청 조건이 너무 좁아 결과가 0건일 때 어떤 제약을 완화할지 "
        "판단하는 도우미다. 반드시 search_events_relaxed 도구를 한 번만 호출하라. "
        "지역과 장르를 둘 다 풀면 사용자의 본래 의도가 흐려지니, 최소한만 푼다."
    )
    user_msg = (
        f"사용자 발화: {query}\n"
        f"적용됐던 location_keywords: {location_keywords or '(없음)'}\n"
        f"적용됐던 music_genre 필터: {genre_filter or '(없음)'}\n"
        f"이 조합으로 후보가 0건이다. 어떤 제약을 완화할지 도구로 답하라."
    )
    try:
        resp = client.chat.completions.create(
            model=os.getenv("EVENT_AGENT_MODEL", "gpt-4o-mini"),
            temperature=0,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            tools=[_RELAX_TOOL_SCHEMA],
            tool_choice={"type": "function", "function": {"name": "search_events_relaxed"}},
        )
        tool_calls = resp.choices[0].message.tool_calls or []
        if not tool_calls:
            return None
        args = json.loads(tool_calls[0].function.arguments)
    except Exception:
        return None
    return {
        "relax_location": bool(args.get("relax_location")),
        "relax_genre": bool(args.get("relax_genre")),
        "note": str(args.get("note") or "").strip(),
    }


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
                "exhibition_type": _event_attr(event, "exhibition_type"),
                "has_image": bool(_event_attr(event, "thumbnail_url")),
                "mood_tags": _listish(_event_attr(event, "new_mood_tags") or _event_attr(event, "mood_tags"))[:5],
                "audience_tags": _listish(_event_attr(event, "new_audience_tags") or _event_attr(event, "audience_tags"))[:5],
                "description": str(_event_attr(event, "description") or "")[:500],
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
    explicit_locations = [str(loc) for loc in (taste_context.get("location_keywords") or []) if loc]
    suppressed = [str(s) for s in (taste_context.get("suppressed_keywords") or []) if s]

    prompt = (
        f"[사용자 질문] {query}\n\n"
        f"[최근 대화 흐름]\n{recent_history or '(첫 대화)'}\n\n"
        f"[사용자 취향 컨텍스트]\n"
        f"{', '.join(taste_terms) if taste_terms else '(취향 정보 없음)'}\n\n"
        f"[사용자 발화에서 추출된 명시적 제약]\n"
        f"- 지역명: {', '.join(explicit_locations) if explicit_locations else '(없음)'}\n"
        f"- 피해야 할 조건: {', '.join(suppressed) if suppressed else '(없음)'}\n\n"
        f"[후보 이벤트]\n{json.dumps(event_summaries, ensure_ascii=False, indent=2)}\n\n"
        f"위 후보 중 사용자 요청에 **실제로** 맞는 이벤트를 최대 {top_k}개 고르세요.\n\n"
        "**[0순위 — 사용자 발화 명시 제약 (아래 모든 우선순위보다 우선):**\n"
        "먼저 위 [사용자 질문]을 한 번 더 그대로 읽고, 사용자가 직접 말한 모든 제약을 존중하세요.\n"
        "- 지역명이 명시된 경우: 후보의 location/description에 해당 지역이 포함된 것만 선정. "
        "성수라고 했는데 강남 이벤트 고르면 안 됨.\n"
        "- '~말고', '~빼고', '~지양', '~피하고' 같은 부정/회피 표현이 있으면 그 조건에 해당하는 후보는 제외. "
        "예: '브랜드 홍보용 말고' → description·태그가 단순 브랜드 마케팅 중심인 팝업 제외, "
        "작가·컨셉·체험 중심 팝업만 선정. '대형 페스티벌 말고' → 소규모/인디 페스티벌만 선정.\n"
        "- 후보 중 명시적 제약을 만족하는 게 하나도 없으면 빈 배열 반환. 제약 어기면서 채우지 마세요.\n\n"
        "**선정 우선순위 (★ 위 0순위 제약을 만족하는 후보 안에서):**\n"
        "- thumbnail_url이 있는 이벤트를 반드시 우선 선정 (없으면 UI에 이미지가 안 나와 사용자 경험이 나빠짐)\n"
        "- mood_tags에 '힙한', '트렌디한', '감각적인', '유니크한', 'SNS감성', '이색적인' 등이 많을수록 우선\n"
        "- 활동적이고 체험형인 이벤트 우선 (직접 참여/체험 가능한 것)\n"
        "- 독특하고 기억에 남을 이벤트 우선 (대중적·평범한 것보다)\n"
        "- 유명 브랜드·아티스트 협업 이벤트 우선\n\n"
        "**필터링 규칙 (★ 반드시 지키기):**\n"
        "- 사용자가 특정 장르/유형을 요청한 경우 (예: '아이돌', '힙합', '재즈', '인디', '트로트') "
        "후보 아티스트/그룹명을 보고 당신의 사전 지식으로 장르를 판단해 일치하는 것만 고르세요.\n"
        "  · '아이돌' = K-pop 보이/걸 그룹 (BTS, 뉴진스, I.O.I, aespa, 세븐틴 등). 인디·솔로 싱어송라이터·트로트·발라드 가수는 제외.\n"
        "  · '인디' = 인디 밴드/싱어송라이터 (닐로, 문없는집, 검정치마 등). 메이저 아이돌 제외.\n"
        "  · '힙합/랩' = 힙합 아티스트 공연. 인디 록·아이돌 제외.\n"
        "- 후보 중 사용자 요청과 맞는 게 **하나도 없으면 빈 배열 반환**. 억지로 채우지 마세요.\n"
        "- 모르는 아티스트는 추측하지 말고 제외하세요.\n\n"
        "**각 선정 이벤트에 대해 다음 순서로 사고:**\n"
        "  1) [의도] 이 이벤트가 '왜 열리는지/어떤 컨셉인지' description에서 추출해 한 문장으로 정리\n"
        "  2) [매칭] 사용자 질문/취향과 자연스럽게 이어지는 포인트를 description·태그 안에서 찾기\n"
        "  3) [추천 이유] 의도와 매칭을 자연스러운 문장으로 엮기 (2-3문장, 존댓말)\n\n"
        "**작성 규칙:**\n"
        "- 이벤트의 description, hashtags, mood_tags 등 후보 데이터에 실제로 있는 내용만 사용 "
        "(이벤트 시간·장소·내용 등 구체 사실 지어내기 금지)\n"
        "- 단, 아티스트 분야/장르 판단에는 당신의 사전 지식 활용 가능\n"
        "- 어색한 표현 금지: \"당신이 좋아하시는 'X'\", \"~카테고리에 부합\", \"평소 선호하시는 동선\"\n"
        "- 키워드를 따옴표로 박아넣지 않기 → 자연스러운 문장으로 녹이기\n"
        "- 작가명/브랜드명/컨셉 등 구체 정보를 우선 활용\n"
        "- \"~한 분께 잘 맞아요\" 같은 부드러운 연결 사용\n"
        "- 콘서트는 description이 빈약하므로 제목·아티스트·장소·날짜 중심으로 짧게 사실 위주\n\n"
        "JSON 형식으로만 반환 (맞는 후보 없으면 recommendations는 빈 배열):\n"
        "{\n"
        '  "recommendations": [\n'
        '    {\n'
        '      "index": 1,\n'
        '      "intent": "이벤트의 의도/컨셉 한 문장",\n'
        '      "match_points": ["매칭 근거 1", "매칭 근거 2"],\n'
        '      "reason": "2-3문장의 자연스러운 추천 이유"\n'
        '    }\n'
        '  ]\n'
        "}"
    )

    try:
        response = client.chat.completions.create(
            model=os.getenv("EVENT_AGENT_MODEL", "gpt-4o-mini"),
            temperature=0.3,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "너는 K-Dive 서비스의 이벤트 큐레이터다.\n"
                        "서울의 팝업스토어·전시·공연·페스티벌 중 사용자 요청과 맞는 후보를 골라 "
                        "'왜 이게 좋은지'를 자연스럽게 설명한다.\n\n"
                        "철칙:\n"
                        "1) 이벤트의 구체 사실(시간·장소·전시 내용·프로그램 등)은 후보 데이터에 있는 것만 사용. 없는 내용 지어내기 금지.\n"
                        "2) 단, 아티스트/브랜드의 '장르·분야 분류'는 너의 사전 지식 활용 가능 "
                        "(예: BTS·뉴진스·I.O.I = K-pop 아이돌, 닐로·문없는집 = 인디, 임영웅 = 트로트). "
                        "사용자가 특정 장르를 요청하면 후보 중 그 장르에 해당하는 것만 골라야 한다.\n"
                        "3) 사용자 요청에 맞는 후보가 없으면 억지로 채우지 말고 빈 배열 반환.\n"
                        "4) 추천 이유는 이벤트의 '컨셉/의도'를 먼저 드러내고, 그 다음 사용자 요청과 연결한다.\n"
                        "5) 기계적·체크리스트형 표현 금지. \"카테고리 부합\", \"키워드 매칭\" 같은 메타적 설명 대신 "
                        "이벤트의 실제 내용으로 설득한다.\n"
                        "6) 친근한 존댓말, 한국어 자연스러운 어투 유지.\n"
                        "7) description이 빈약한 콘서트는 무리해서 길게 쓰지 말고 사실 위주로 짧게."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content or "{}"
        data = json.loads(raw)
    except Exception:
        return None  # LLM 호출 실패 — 폴백 필요

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
    return cards  # 빈 배열 = LLM이 의도적으로 비움 (맞는 후보 없음)


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


def _merge_with_vector_search(
    keyword_results: list[dict[str, Any]],
    query: str,
    mood: str,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """벡터 검색을 1차로 사용하고 키워드 검색 결과로 보완한다.

    벡터(의미 기반)가 동의어·유사 표현을 잡고, 키워드(글자 매칭)는
    아티스트명·브랜드명처럼 정확한 토큰이 필요한 케이스를 보충한다.
    벡터 검색이 사용 불가하면 키워드 결과로 폴백한다.
    """
    try:
        from apps.agents.workers.event.vector_store import get_events_by_ids, query_events
    except Exception:
        return keyword_results

    # 카테고리가 명확하면 필터링해서 검색, 결과 없으면 전체에서 재시도
    detected_category = _detect_category(query, mood)
    vector_results = query_events(
        query=query.strip(),
        top_k=limit,
        category_filter=detected_category,
    )
    if not vector_results and detected_category:
        vector_results = query_events(query=query.strip(), top_k=limit)

    vector_ids = [r["event_id"] for r in vector_results if r.get("event_id")]
    vector_events = get_events_by_ids(vector_ids)

    # chroma 미빌드 등으로 벡터 검색 실패 → 키워드 결과로 폴백
    if not vector_events:
        return keyword_results

    # 두 신호를 라운드로빈으로 인터리브: 벡터 1개·키워드 1개씩 번갈아 채운다.
    # 벡터 단독으로 limit 채우면 키워드 결과가 LLM 컨텍스트에 못 들어가므로
    # 의미 기반/글자 매칭 둘 다 상위에 노출되도록 보장한다 (예: '아이돌 콘서트'에서
    # 벡터가 인디 가수를 올려도 키워드가 잡은 실제 아이돌이 같은 후보 풀에 들어옴).
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for vec_ev, kw_ev in zip_longest(vector_events, keyword_results):
        for candidate in (vec_ev, kw_ev):
            if candidate is None:
                continue
            eid = str(candidate.get("id", ""))
            if eid and eid in seen:
                continue
            seen.add(eid)
            merged.append(candidate)
            if len(merged) >= limit:
                return merged
    return merged


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


def _fix_detail_url(url: str | None) -> str | None:
    """멜론 URL 형식 변환: #/perf/213024 → ?prodId=213024"""
    if not url:
        return url
    import re
    match = re.search(r'ticket\.melon\.com.*[#/]perf/(\d+)', url)
    if match:
        return f"https://ticket.melon.com/performance/index.htm?prodId={match.group(1)}"
    return url


def _fix_thumbnail_url(url: str | None) -> str | None:
    """야놀자 썸네일 URL의 저화질 파라미터를 고화질로 교체."""
    if not url:
        return url
    import re
    url = re.sub(r'width=\d+', 'width=400', url)
    url = re.sub(r'quality=\d+', 'quality=85', url)
    return url


def _event_to_card(event: Any, reason: str) -> dict[str, Any]:
    title = str(_event_attr(event, "title") or "이벤트")
    category = _event_attr(event, "new_main_category") or _event_attr(event, "category") or "이벤트"
    subcategory = _event_attr(event, "new_sub_category")
    photo = _fix_thumbnail_url(_event_attr(event, "thumbnail_url"))
    return {
        "id": _event_attr(event, "id") or title,
        "title": title,
        "name": title,
        "location": _event_attr(event, "location") or "",
        "address": _event_attr(event, "location") or "",
        "region": _event_attr(event, "region") or "",
        "category": " · ".join(str(item) for item in (category, subcategory) if item),
        "date": _date_range(event),
        "thumbnail_url": photo,
        "photo_url": photo,
        "photo_urls": [url for url in (photo,) if url],
        "detail_url": _fix_detail_url(_event_attr(event, "detail_url")),
        "store_url": _fix_detail_url(_event_attr(event, "store_url")),
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
