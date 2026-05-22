"""
Event Worker Agent — LangGraph 노드 함수 모음

[역할]
각 노드는 EventGraphState를 받아서 EventGraphState를 돌려준다.
기존 agent.py 의 비즈니스 로직(검색·필터·LLM 호출)을 그대로 재사용하고,
이 파일은 "노드 어댑터" 역할만 한다.

[노드 목록]
1. prepare_node   — taste_context 에서 mood/location/genre 추출
2. search_node    — 키워드 + 벡터 검색 (병합 포함)
3. filter_node    — 지역/장르 하드 필터
4. relax_node     — 후보 0건일 때 LLM에게 제약 완화 요청 + 재검색
5. curate_node    — LLM 큐레이션 (취향 기반 카드 생성)
6. format_node    — 최종 응답 메시지 포맷팅
"""

from __future__ import annotations

from typing import Any
from typing_extensions import TypedDict, NotRequired

# 기존 agent.py 의 함수들을 재사용 (재구현 X)
from .agent import (
    DEFAULT_EVENT_TOP_K,
    CURATION_CANDIDATE_LIMIT,
    SEOUL_AREAS,
    search_events_from_db,
    _merge_with_vector_search,
    _filter_by_explicit_location,
    _filter_by_genre,
    _ask_llm_for_relaxation,
    _event_mood_from_taste,
    _detect_genre_filter,
    _detect_category,
    _build_event_response_message,
    _event_to_card,
    _fallback_reason,
    curate_events_with_llm,
)

# music_genre 데이터가 있는 카테고리에만 장르 하드 필터를 적용한다.
# 팝업/전시는 본질적으로 music_genre가 비어있어 필터를 걸면 무조건 0건이 된다.
_GENRE_RELEVANT_CATEGORIES = {"공연", "페스티벌"}


# ============================================================
# State 정의 — 노드들이 공유하는 데이터
# ============================================================


class EventGraphState(TypedDict):
    """이벤트 에이전트 그래프 내부 상태.

    Supervisor 와 통합할 때는 KDiveState 와 이 State 사이를 매핑한다.
    (그래프 내부 단계가 단순해지도록 일부러 평탄한 구조로 둔다.)
    """

    # ===== 입력 (그래프 시작 시 채워짐) =====
    query: str
    taste_context: dict
    history: list[dict]
    top_k: int

    # ===== prepare_node 출력 =====
    mood: NotRequired[str]
    location_keywords: NotRequired[list[str]]
    genre_filter: NotRequired[list[str]]

    # ===== search_node 출력 =====
    raw_candidates: NotRequired[list[dict]]

    # ===== filter_node 출력 =====
    candidates: NotRequired[list[dict]]

    # ===== relax_node 출력 =====
    relax_note: NotRequired[str]
    curate_taste_context: NotRequired[dict]

    # ===== curate_node 출력 =====
    curated_cards: NotRequired[list[dict]]

    # ===== 최종 출력 =====
    result: NotRequired[dict]


# ============================================================
# 노드 1: prepare — taste_context 분해
# ============================================================


def prepare_node(state: EventGraphState) -> EventGraphState:
    """taste_context 에서 필요한 값을 꺼내 state 평탄화.

    taste_context 의 location_keywords / preferred_music 를 1차 신호로 쓰고,
    raw query 추론은 fallback 으로 합친다. 그래야 search 단계 후보가
    사용자 취향을 반영해서 잡혀 LLM relaxation 호출이 줄어든다.
    """
    from .agent import _safe_str_list  # 방어 처리된 평탄화 헬퍼

    query = state["query"]
    taste_context = state.get("taste_context") or {}

    state["mood"] = _event_mood_from_taste(taste_context)

    # 위치: taste_context 우선, query 에서 추가로 발견되면 합집합
    ctx_locations = _safe_str_list(taste_context.get("location_keywords"))
    query_locations = [area for area in SEOUL_AREAS if area in (query or "")]
    state["location_keywords"] = list(dict.fromkeys([*ctx_locations, *query_locations]))

    # 장르: taste_context.preferred_music 을 1차로 사용, query/mood 매칭은 fallback
    ctx_music = _safe_str_list(taste_context.get("preferred_music"))
    detected = _detect_genre_filter(query, state["mood"])
    state["genre_filter"] = list(dict.fromkeys([*ctx_music, *detected]))

    state["curate_taste_context"] = dict(taste_context)
    state["relax_note"] = ""
    return state


# ============================================================
# 노드 2: search — 키워드 + 벡터 검색 병합
# ============================================================


def search_node(state: EventGraphState) -> EventGraphState:
    """DB 키워드 검색 + 벡터 검색 결과를 병합해 raw_candidates 채움.

    taste_context 에서 prepare_node 가 모아둔 location_keywords 를 검색 쿼리에
    합쳐서, 사용자가 raw query 에 지역명을 안 써도 후보가 그쪽으로 잡히게 한다.
    그래야 filter 단계에서 0건이 나와 relax_node 가 LLM 을 호출하는 경로가
    줄어든다 (피드백: "taste_context 우선, raw query 추론은 fallback").
    """
    query = state["query"]
    mood = state.get("mood", "")
    location_keywords = state.get("location_keywords") or []

    # raw query 에 이미 들어있지 않은 위치 키워드만 덧붙임 (중복 회피)
    extra = [loc for loc in location_keywords if loc and loc not in (query or "")]
    enriched_query = " ".join([query, *extra]).strip() if extra else query

    try:
        events = search_events_from_db(query=enriched_query, mood=mood, limit=20)
        events = _merge_with_vector_search(events, query=enriched_query, mood=mood, limit=20)
    except Exception as exc:
        state["result"] = {
            "status": "error",
            "message": f"Event DB 조회 중 오류가 발생했어요: {exc}",
            "recommended_events": [],
        }
        events = []

    state["raw_candidates"] = events
    return state


# ============================================================
# 노드 3: filter — 지역/장르 하드 필터
# ============================================================


def filter_node(state: EventGraphState) -> EventGraphState:
    """raw_candidates 에 location/genre 하드 필터를 적용해 candidates 생성."""
    # search 단계에서 이미 result 가 채워졌으면(에러) 그대로 통과
    if state.get("result"):
        state["candidates"] = []
        return state

    events = state.get("raw_candidates") or []
    location_keywords = state.get("location_keywords") or []
    genre_filter = state.get("genre_filter") or []

    if location_keywords:
        events = _filter_by_explicit_location(events, location_keywords)
    # 팝업/전시는 music_genre가 비어있는 게 정상이라 장르 필터를 걸면 무조건 0건.
    # 사용자가 명시적으로 공연/페스티벌을 요청한 경우에만 장르 하드 필터 적용.
    detected_category = _detect_category(state.get("query") or "", state.get("mood") or "")
    if genre_filter and detected_category in _GENRE_RELEVANT_CATEGORIES:
        events = _filter_by_genre(events, genre_filter)

    state["candidates"] = events
    return state


# ============================================================
# 노드 4: relax — 후보 0건일 때 제약 완화
# ============================================================


def relax_node(state: EventGraphState) -> EventGraphState:
    """후보 0건일 때 제약 완화.

    제약이 하나뿐이면 그걸 풀 수밖에 없으므로 LLM 호출을 건너뛰고 룰로 처리.
    둘 다 걸려있을 때만 LLM 에게 "어느 쪽을 풀까" 물어본다.
    """
    query = state["query"]
    mood = state.get("mood", "")
    location_keywords = state.get("location_keywords") or []
    genre_filter = state.get("genre_filter") or []

    # 풀 만한 제약 없음 → 그대로 통과
    if not location_keywords and not genre_filter:
        return state

    # 룰 기반: 제약이 하나뿐이면 LLM 호출 없이 그걸 푼다
    if bool(location_keywords) ^ bool(genre_filter):
        relaxation = {
            "relax_location": bool(location_keywords),
            "relax_genre": bool(genre_filter),
            "note": "",
        }
    else:
        relaxation = _ask_llm_for_relaxation(
            query=query,
            location_keywords=location_keywords,
            genre_filter=genre_filter,
        )
        if not relaxation:
            return state

    relaxed_loc = [] if relaxation.get("relax_location") else location_keywords
    relaxed_genre = [] if relaxation.get("relax_genre") else genre_filter
    if relaxed_loc == location_keywords and relaxed_genre == genre_filter:
        return state

    # 재검색 (search + 완화된 필터)
    # location 이 살아있으면 검색 쿼리에도 합쳐서 후보 풀을 그쪽으로 유도
    extra = [loc for loc in relaxed_loc if loc and loc not in (query or "")]
    enriched_query = " ".join([query, *extra]).strip() if extra else query
    try:
        events = search_events_from_db(query=enriched_query, mood=mood, limit=20)
        events = _merge_with_vector_search(events, query=enriched_query, mood=mood, limit=20)
        if relaxed_loc:
            events = _filter_by_explicit_location(events, relaxed_loc)
        if relaxed_genre:
            events = _filter_by_genre(events, relaxed_genre)
    except Exception:
        events = []

    if events:
        state["candidates"] = events
        state["relax_note"] = relaxation.get("note") or ""
        # curate 단계에 넘길 taste_context 에서도 풀어준 제약을 제거
        # (그렇지 않으면 LLM 프롬프트의 "지역명 명시 제약" 룰이 다시 후보를 거름)
        curate_ctx = dict(state.get("curate_taste_context") or {})
        if relaxation.get("relax_location"):
            curate_ctx["location_keywords"] = []
        state["curate_taste_context"] = curate_ctx

    return state


# ============================================================
# 노드 5: curate — LLM 큐레이션
# ============================================================


def curate_node(state: EventGraphState) -> EventGraphState:
    """후보를 LLM 에 넘겨 top_k 개의 추천 카드를 만든다."""
    # 앞 단계에서 에러로 result 가 이미 채워졌으면 그대로 통과
    if state.get("result"):
        return state

    candidates = state.get("candidates") or []
    query = state["query"]
    top_k = state.get("top_k", DEFAULT_EVENT_TOP_K)
    curate_ctx = state.get("curate_taste_context") or state.get("taste_context") or {}
    history = state.get("history") or []

    # 완화까지 했는데도 0건 → no_results 응답으로 종료
    if not candidates:
        state["result"] = {
            "status": "no_results",
            "message": "조건에 맞는 이벤트 추천을 찾지 못했어요. 지역이나 이벤트 종류를 조금 더 알려주시면 다시 찾아볼게요.",
            "recommended_events": [],
        }
        state["curated_cards"] = []
        return state

    # LLM 프롬프트 토큰/지연 줄이기 위해 상위 N개만 넘긴다.
    # candidates 는 이미 _event_score 로 정렬돼있으므로 앞에서 자르면 점수 상위.
    curated = curate_events_with_llm(
        events=candidates[:CURATION_CANDIDATE_LIMIT],
        query=query,
        taste_context=curate_ctx,
        history=history,
        top_k=top_k,
    )

    # curated = None: LLM 호출 실패 → 후보 앞에서 폴백 카드 생성
    if curated is None:
        curated = [
            _event_to_card(ev, reason=_fallback_reason(ev, query))
            for ev in candidates[:top_k]
        ]
    # curated = []: LLM 이 의도적으로 비움 (맞는 후보 없음)
    elif not curated:
        state["result"] = {
            "status": "no_results",
            "message": "요청하신 조건에 딱 맞는 이벤트를 찾지 못했어요. 다른 장르나 키워드로 다시 알려주시면 더 잘 찾아드릴게요.",
            "recommended_events": [],
        }
        state["curated_cards"] = []
        return state

    state["curated_cards"] = curated[:top_k]
    return state


# ============================================================
# 노드 6: format — 최종 응답 메시지 포맷
# ============================================================


def format_node(state: EventGraphState) -> EventGraphState:
    """카드 + 안내 메시지를 묶어 최종 응답 객체를 만든다."""
    # 앞 단계에서 result 가 이미 채워졌으면 그대로 사용
    if state.get("result"):
        return state

    query = state["query"]
    curated = state.get("curated_cards") or []
    relax_note = state.get("relax_note", "")
    curate_ctx = state.get("curate_taste_context") or state.get("taste_context") or {}

    final_msg = _build_event_response_message(
        query, curate_ctx, curated, relax_note=relax_note,
    )
    state["result"] = {
        "status": "ok",
        "message": final_msg,
        "relaxation_note": relax_note,
        "recommended_events": curated,
    }
    return state


# ============================================================
# 조건 분기 함수 — 다음 노드를 결정
# ============================================================


def route_after_filter(state: EventGraphState) -> str:
    """필터 후 후보가 있는지로 분기.

    - 에러로 result 가 이미 있으면 → format 로 직행 (그대로 결과 반환)
    - 후보 있음 → curate 로
    - 후보 없음 → relax 로 (제약 완화 시도)
    """
    if state.get("result"):
        return "format"
    if state.get("candidates"):
        return "curate"
    return "relax"
