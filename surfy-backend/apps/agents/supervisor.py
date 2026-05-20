"""
K-Dive Supervisor Agent
사용자 요청을 분석하고 적절한 전문 에이전트로 라우팅하는 모듈

흐름:
  supervisor_intake()
    1. 키워드 추출        → extract_keywords_from_utterance()
    2. 온보딩 매칭 확인   → check_onboarding_match()
    3. TPO 충돌 감지      → detect_tpo_conflict()
    4. 취향 객체 구성     → build_taste_context() + build_keywords_with_reasons()
    5. 라우팅 결정        → decide_target_agents()
"""

import os
import re
from datetime import date
from typing import Optional

from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from .utils import get_seoul_now

from .state import (
    KDiveState,
    OnboardingData,
    KeywordWithReason,
    PreviousTurn,
    TravelPhase,
    AGENT_TOURIST,
    AGENT_FOODIE,
    AGENT_EVENT,
    WEIGHT_CURRENT_UTTERANCE,
    WEIGHT_ONBOARDING,
    REACTION_POSITIVE,
    REACTION_NEGATIVE,
    REACTION_NONE,
)

# ============================================================
# 상수
# ============================================================

# 발화 내 부정 표현 패턴 (억제 키워드 감지용)
_NEGATIVE_PATTERNS = (
    "싫어", "싫은", "싫다", "싫음", "이 싫",
    "안 좋아", "별로", "피하고 싶", "원하지 않", "없는 곳", "제외",
    "그만", "가기 싫", "보기 싫", "지겨", "질리", "안 가고", "안 보고",
    "보고싶지 않", "가고싶지 않", "하고싶지 않", "싶지 않",
    "말고", "빼고", "제외하고", "말구",
)

# 위치 키워드 정규화용 — 온보딩/주소 매칭 전에 떼어낼 표현
# - 꾸밈말 ("남산 근처" → "남산") : 온보딩 항목 매칭용
# - 지하철역 접미사 ("혜화역" → "혜화") : 주소에는 역명이 들어가지 않으므로 필요
_LOCATION_MODIFIERS = ("근처", "주변", "근방", "인근", "일대", "쪽", "역")

# 발화에 등장하면 관광(tourist) 의도가 명확한 표현
# LLM이 행동 동사(구경/산책 등)를 activity/other 로 분류해 tourist 표를 못 받는 경우를 보강한다.
_TOURIST_INTENT_TERMS = (
    "관광", "관광지", "여행지", "명소", "가볼만", "구경",
    "산책", "박물관", "미술관", "공원", "야경", "볼거리",
)

# 명시적으로 배제(suppress)되어야 할 어휘 — "X 말고/빼고" 형태로 함께 등장한다.
# LLM이 부정 대상을 키워드로 추출하지 않을 때 결정적으로 잡는다.
_EXPLICIT_EXCLUDE_TERMS = (
    "체인", "프랜차이즈",
    "스타벅스", "커피빈", "투썸", "이디야", "메가커피",
    "컴포즈", "빽다방", "할리스", "폴바셋", "파스쿠찌",
    "엔제리너스", "탐앤탐스",
)

# "로컬/동네/개인/독립/숨은" 의도가 발화에 있으면 "체인"을 자동으로 suppress 한다.
# (dummy_server._detect_suppressed_keywords 와 동일 정책)
_LOCAL_INTENT_TERMS = ("로컬", "동네", "개인", "독립", "숨은")

# 너무 광범위해서 특정 장소명 매칭의 근거가 될 수 없는 지명
# "서울" 이 "남산서울타워" 에 부분 문자열로 우연히 걸리는 것을 막는다.
_GENERIC_LOCATIONS = {"서울", "한국", "대한민국", "경기", "경기도"}

# 서비스 범위(수도권) 판단용 지명 목록 — 발화 원문을 직접 스캔한다.
# LLM 키워드 추출이 지명을 누락해도 동작하도록 결정적(deterministic) 게이트로 사용.
# 부분 문자열로 매칭하므로, 일반 단어와 겹치기 쉬운 지명(세종, 강화, 양주 등)은
# 의도적으로 제외했다. 필요 시 운영하며 목록을 보강한다.
_OUT_OF_SCOPE_REGIONS = frozenset({
    # 광역시·도
    "부산", "대구", "대전", "울산", "광주광역시",
    "강원", "강원도", "충청", "충청북도", "충청남도", "충북", "충남",
    "전라", "전라북도", "전라남도", "전북", "전남",
    "경상", "경상북도", "경상남도", "경북", "경남",
    "제주", "제주도", "제주특별자치도",
    # 주요 도시·관광지
    "해운대", "광안리", "강릉", "속초", "양양", "춘천", "평창", "정선",
    "원주", "삼척", "청주", "천안", "충주", "단양", "공주", "부여", "보령",
    "전주", "군산", "여수", "순천", "목포", "광양",
    "경주", "포항", "안동", "구미", "창원", "김해", "진주", "통영", "거제", "남해",
    "울릉도", "독도", "설악산", "지리산", "한라산",
})

# 수도권(서울·경기·인천) 지명 목록 — LLM이 놓친 지명을 location 키워드로 보강한다.
_CAPITAL_AREA_REGIONS = frozenset({
    # 광역
    "서울", "경기", "경기도", "인천", "수도권",
    # 서울 자치구
    "강남", "강동", "강북", "강서", "관악", "광진", "구로", "금천", "노원",
    "도봉", "동대문", "동작", "마포", "서대문", "서초", "성동", "성북",
    "송파", "양천", "영등포", "용산", "은평", "종로", "중랑",
    # 서울 주요 지명
    "홍대", "이태원", "명동", "압구정", "청담", "성수", "연남", "망원",
    "북촌", "서촌", "인사동", "여의도", "잠실", "신촌", "가로수길",
    "한남동", "을지로", "익선동", "남산", "한강", "혜화", "대학로",
    # 경기 시·군
    "수원", "성남", "분당", "판교", "용인", "고양", "일산", "부천", "안양",
    "안산", "화성", "평택", "의정부", "시흥", "파주", "김포", "광명", "군포",
    "하남", "오산", "안성", "포천", "의왕", "여주", "동두천",
    "과천", "남양주", "가평", "양평", "연천",
    # 인천
    "송도", "월미도", "강화도", "영종도", "부평", "차이나타운",
})

# ============================================================
# LLM 초기화 (지연 초기화 — 실제 호출 시점에 생성)
# ============================================================

_llm_instance: "ChatOpenAI | None" = None


def _get_llm() -> "ChatOpenAI":
    """LLM 인스턴스를 반환한다. 처음 호출될 때 한 번만 생성한다."""
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = ChatOpenAI(
            model=os.getenv("SUPERVISOR_MODEL", "gpt-4o-mini"),
            temperature=0,
        )
    return _llm_instance

# ============================================================
# Pydantic 스키마 (LLM 구조화 출력 전용)
# ============================================================


class _ExtractedKeyword(BaseModel):
    keyword: str = Field(description="추출된 키워드 (원문 또는 정규화 표현, 한국어 유지)")
    category: str = Field(
        description="place_type | mood | location | food_type | event_type | activity | other"
    )
    agent_hint: str = Field(
        description="이 키워드를 담당할 에이전트: tourist | foodie | event | any"
    )
    is_past_action: bool = Field(
        default=False,
        description="이미 완료된 행동이면 True (예: '구경했는데', '다녀왔는데'). "
                    "True이면 라우팅 투표에서 제외되어 배경 맥락으로만 사용된다.",
    )


class _KeywordExtractionResult(BaseModel):
    keywords: list[_ExtractedKeyword]


class _TravelPhaseResult(BaseModel):
    travel_phase: str = Field(
        description=(
            "사용자가 여행을 계획 중이면 'pre_trip', "
            "현재 여행 중(이동/탐색 중)이면 'during_trip', "
            "판단 불가면 'unknown'"
        )
    )


# ============================================================
# Supervisor 메인 함수
# ============================================================


def supervisor_intake(state: KDiveState) -> KDiveState:
    """
    앞단 Supervisor: 사용자 요청을 분석하고 라우팅을 결정한다.

    [흐름]
    1. 키워드 추출 (LLM)
    2. 온보딩 매칭 확인 (Q1)
    3. TPO 충돌 감지 (Q2)
    4. 취향 객체 구성 (Q1 + Q5 + Q7)
    5. 라우팅 결정

    Args:
        state: KDiveState (사용자 발화, 온보딩 데이터, 이전 턴 정보 포함)

    Returns:
        KDiveState: 라우팅 결정과 취향 객체가 추가된 상태
    """
    previous_turn: Optional[PreviousTurn] = state.get("previous_turn")

    # ----- 0. 대화 히스토리 누적 (멀티턴) -----
    conv_messages: list[dict] = list(state.get("messages") or [])
    conv_messages.append({"role": "user", "content": state["user_utterance"]})
    state["messages"] = conv_messages

    # ----- 0.3. 현재 시각 주입 (Asia/Seoul) -----
    seoul_now = get_seoul_now()
    today = seoul_now.date()
    current_date_str = f"{today.year}년 {today.month}월 {today.day}일"
    state["current_datetime"] = current_date_str

    # ----- 0.5. 과거 날짜 감지 (정규식) -----
    is_past, detected_date = _detect_past_date(state["user_utterance"], today)
    if is_past:
        state["needs_user_clarification"] = True
        state["clarification_type"] = "past_date"
        state["clarification_question"] = (
            f"말씀하신 '{detected_date}'은(는) 이미 지난 날짜예요.\n"
            f"현재 날짜({current_date_str}) 기준으로 추천해드릴까요?\n"
            f"아니면 다른 날짜를 알려주시면 그 기준으로 도와드릴게요!"
        )
        return state

    # ----- 0.7. 여행 단계 감지 -----
    state["travel_phase"] = _detect_travel_phase(state["user_utterance"])

    # ----- 1. 키워드 추출 (LLM) — 현재 날짜 주입으로 날짜 인식 가능 -----
    extracted_keywords = extract_keywords_from_utterance(
        utterance=state["user_utterance"],
        current_date_str=current_date_str,
        messages=conv_messages,           # 직전 1턴 → "거기서" 대명사 해석용
        accumulated_keywords=state.get("accumulated_keywords"),  # 누적 컨텍스트 주입
    )

    # 범위 밖 안내 후 이어진 발화면, 직전에 보관한 키워드를 합친다
    carried = state.pop("_carried_keywords", None)
    if carried:
        existing = {kw.keyword for kw in extracted_keywords}
        extracted_keywords = extracted_keywords + [
            _ExtractedKeyword(**c) for c in carried if c["keyword"] not in existing
        ]

    # ----- 1.5. 서비스 범위 확인 (수도권 지명 목록을 발화 원문에서 직접 스캔) -----
    # LLM 추출이 지명을 누락해도 동작하도록 결정적 게이트를 사용한다.
    out_of_scope_regions, capital_area_regions = detect_region_scope(
        state["user_utterance"]
    )

    # 수도권 지명 보강: LLM이 놓친 수도권 지명을 location 키워드로 추가
    # 중요: LLM이 지명을 location 이 아닌 다른 카테고리(place_type/activity 등)로 잘못 분류한 경우에도
    # 보강이 동작해야 하므로, "location 카테고리 키워드 중에" 해당 지명이 있는지로만 판단한다.
    # (단순히 어떤 키워드에든 지명이 들어있으면 skip 하면, 지명이 place_type 으로 분류됐을 때
    #  location 보강이 누락되어 anchor 모드 오동작·위치 무시로 이어진다.)
    for region in capital_area_regions:
        has_location_match = any(
            kw.category == "location" and region in kw.keyword
            for kw in extracted_keywords
        )
        if not has_location_match:
            extracted_keywords.append(
                _ExtractedKeyword(
                    keyword=region, category="location", agent_hint="any"
                )
            )

    # tourist 의도 보강: LLM이 행동 동사를 tourist 로 라우팅하지 못한 경우를 보완
    # 같은 어휘를 LLM이 'any' 등 다른 hint 로 추출하거나 is_past_action=True 로 잡아
    # 라우팅 투표에서 빠지는 경우가 있어, "라우팅에 실제로 표를 줄 살아있는 tourist 키워드" 가
    # 있는지로만 dedup 한다.
    existing_live_tourist_terms = {
        kw.keyword
        for kw in extracted_keywords
        if kw.agent_hint == "tourist" and not kw.is_past_action
    }
    for term in _scan_tourist_intent_terms(state["user_utterance"]):
        if term in existing_live_tourist_terms:
            continue
        extracted_keywords.append(
            _ExtractedKeyword(
                keyword=term, category="activity", agent_hint="tourist"
            )
        )
        existing_live_tourist_terms.add(term)

    # 수도권 밖 지명이 있으면 라우팅하지 않고 사용자를 수도권으로 유도
    if out_of_scope_regions:
        state["needs_user_clarification"] = True
        state["clarification_type"] = "out_of_scope"
        state["clarification_question"] = _build_out_of_scope_question(
            out_of_scope_regions
        )
        # 범위 밖 지명을 포함하지 않는 키워드는 다음 발화로 이어받는다
        state["_carried_keywords"] = [
            {
                "keyword": kw.keyword,
                "category": kw.category,
                "agent_hint": kw.agent_hint,
                "is_past_action": kw.is_past_action,
            }
            for kw in extracted_keywords
            if not any(r in kw.keyword for r in out_of_scope_regions)
        ]
        return state

    # ----- 2. 온보딩 매칭 확인 (Q1) -----
    is_matching_sufficient = check_onboarding_match(
        keywords=extracted_keywords,
        onboarding_data=state["onboarding_data"],
    )

    if not is_matching_sufficient:
        # 추가 질문 1개로 해결 가능한지 판단
        clarification = generate_clarification_question(
            keywords=extracted_keywords,
            onboarding_data=state["onboarding_data"],
        )
        if clarification is not None:
            state["needs_user_clarification"] = True
            state["clarification_question"] = clarification
            return state
        # 추론 가능하면 그대로 진행

    # ----- 3. TPO 충돌 감지 (Q2) -----
    has_conflict = detect_tpo_conflict(
        keywords=extracted_keywords,
        onboarding_data=state["onboarding_data"],
    )

    if has_conflict:
        state["has_tpo_conflict"] = True
        state["needs_user_clarification"] = True
        state["clarification_question"] = build_conflict_question(
            keywords=extracted_keywords,
            onboarding_data=state["onboarding_data"],
        )
        # 이미 추출한 키워드를 저장해두어 사용자 선택 후 이어서 처리할 수 있게 함
        state["_pending_keywords"] = [
            {"keyword": kw.keyword, "category": kw.category, "agent_hint": kw.agent_hint, "is_past_action": kw.is_past_action}
            for kw in extracted_keywords
        ]
        return state

    # ----- 4. 취향 객체 구성 (Q1 + Q5 + Q7) -----
    keywords_with_reasons = build_keywords_with_reasons(
        extracted_keywords=extracted_keywords,
        onboarding_data=state["onboarding_data"],
        previous_turn=previous_turn,
    )

    taste_context = build_taste_context(
        extracted_keywords=extracted_keywords,
        onboarding_data=state["onboarding_data"],
        previous_turn=previous_turn,
    )
    taste_context["allow_onboarding_anchors"] = _should_allow_onboarding_anchors(
        state["user_utterance"], extracted_keywords
    )
    _apply_deterministic_taste_boost(taste_context, state["user_utterance"])

    # ----- 4.5. accumulated_keywords 업데이트 (멀티턴 누적 컨텍스트) -----
    state["accumulated_keywords"] = _merge_accumulated_keywords(
        current_keywords=extracted_keywords,
        taste_context=taste_context,
        previous=state.get("accumulated_keywords"),
    )
    taste_context["conversation_context"] = _build_conversation_context(
        messages=conv_messages,
        accumulated_keywords=state.get("accumulated_keywords"),
        previous_turn=previous_turn,
    )

    # ----- 5. 라우팅 결정 -----
    if is_routing_ambiguous(extracted_keywords):
        # 의도가 애매 → 사용자에게 에이전트 종류 질문
        state["needs_user_clarification"] = True
        state["clarification_type"] = "routing"
        state["clarification_question"] = _build_routing_question()
        state["_pending_keywords"] = [
            {"keyword": kw.keyword, "category": kw.category, "agent_hint": kw.agent_hint, "is_past_action": kw.is_past_action}
            for kw in extracted_keywords
        ]
        # 취향 객체는 미리 구성해서 저장 (질문 해소 후 재사용)
        state["taste_context"] = taste_context
        state["keywords_with_reasons"] = keywords_with_reasons
        return state

    target_agents = decide_target_agents(extracted_keywords=extracted_keywords)
    state["agent_taste_contexts"] = build_agent_taste_contexts(
        extracted_keywords=extracted_keywords,
        target_agents=target_agents,
        onboarding_data=state["onboarding_data"],
        previous_turn=previous_turn,
        base_taste_context=taste_context,
    )

    # ----- 결과를 State에 담기 -----
    state["keywords_with_reasons"] = keywords_with_reasons
    state["taste_context"] = taste_context
    state["target_agents"] = target_agents
    state["needs_user_clarification"] = False

    return state


def build_agent_taste_contexts(
    extracted_keywords: list[_ExtractedKeyword],
    target_agents: list[str],
    onboarding_data: OnboardingData,
    previous_turn: Optional[PreviousTurn],
    base_taste_context: dict,
    tpo_choice: Optional[str] = None,
    onboarding_mood_keywords: Optional[list[str]] = None,
) -> dict[str, dict]:
    """각 Worker가 자기 의도 키워드만 받도록 taste_context를 분리한다."""
    contexts: dict[str, dict] = {}
    for agent in target_agents:
        agent_keywords = [
            kw for kw in extracted_keywords if _keyword_belongs_to_agent(kw, agent)
        ]
        context = build_taste_context(
            extracted_keywords=agent_keywords,
            onboarding_data=onboarding_data,
            previous_turn=previous_turn,
            tpo_choice=tpo_choice,
            onboarding_mood_keywords=onboarding_mood_keywords,
        )
        for key in (
            "allow_onboarding_anchors",
            "conversation_context",
            "suppressed_keywords",
            "boosted_keywords",
        ):
            if key in base_taste_context:
                if key in ("suppressed_keywords", "boosted_keywords"):
                    context[key] = list(base_taste_context.get(key) or [])
                else:
                    context[key] = base_taste_context[key]
        contexts[agent] = context
    return contexts


def _keyword_belongs_to_agent(kw: _ExtractedKeyword, agent: str) -> bool:
    """location/mood는 공유하고, 의도 키워드는 담당 agent에만 배정한다."""
    if kw.category in ("location", "mood"):
        return True
    if kw.agent_hint == agent:
        return True
    if kw.category == "place_type" and kw.agent_hint == "any":
        return agent == AGENT_TOURIST
    return False


def _build_conversation_context(
    messages: list[dict],
    accumulated_keywords: Optional[dict],
    previous_turn: Optional[PreviousTurn],
) -> dict:
    """Worker에 전달할 멀티턴 요약 컨텍스트를 만든다."""
    recent_messages = [
        {"role": msg.get("role"), "content": str(msg.get("content", ""))[:120]}
        for msg in messages[-3:]
    ]
    return {
        "recent_messages": recent_messages,
        "accumulated_keywords": accumulated_keywords or {},
        "last_recommendation": (
            previous_turn.get("last_recommendation") if previous_turn else []
        ) or [],
        "last_keywords": (
            previous_turn.get("last_keywords") if previous_turn else []
        ) or [],
        "user_reaction": (
            previous_turn.get("user_reaction") if previous_turn else REACTION_NONE
        ),
    }


def _is_contextual_followup(utterance: str) -> bool:
    """직전 장소/조건을 현재 발화에 이어받아야 하는지 판단한다."""
    markers = (
        "거기", "그곳", "그 근처", "그 주변", "근처", "주변", "가까운",
        "이어서", "다음으로", "거기서", "거기 근처", "방금",
    )
    return any(marker in utterance for marker in markers)


def _merge_accumulated_keywords(
    current_keywords: list,
    taste_context: dict,
    previous: Optional[dict] = None,
) -> dict:
    """
    현재 턴의 추출 키워드를 이전 누적 컨텍스트에 병합한다.

    카테고리별 병합 규칙:
    - location, place_type, food_type : 교체 — 현재 발화 의도가 이전 것을 덮음
    - mood                           : 누적 — 선호 분위기는 계속 기억
    - suppressed                     : 누적 — 거부 의사는 끝까지 유지

    Args:
        current_keywords: 현재 턴에서 추출된 _ExtractedKeyword 목록
        taste_context: build_taste_context() 반환값 (suppressed_keywords 포함)
        previous: 이전 턴의 accumulated_keywords (없으면 빈 dict)
    """
    prev = dict(previous) if previous else {}

    # 현재 턴 카테고리별 수집
    cur_location  = [kw.keyword for kw in current_keywords if kw.category == "location"]
    cur_place     = [kw.keyword for kw in current_keywords if kw.category == "place_type"]
    cur_food      = [kw.keyword for kw in current_keywords if kw.category == "food_type"]
    cur_mood      = [kw.keyword for kw in current_keywords if kw.category == "mood"]

    result: dict = {}

    # 교체형: 현재 값이 있으면 교체, 없으면 이전 값 유지
    result["location"]   = cur_location  if cur_location  else prev.get("location",   [])
    result["place_type"] = cur_place     if cur_place     else prev.get("place_type",  [])
    result["food_type"]  = cur_food      if cur_food      else prev.get("food_type",   [])

    # 누적형: 이전 + 현재, 삽입 순서 유지 dedup
    prev_mood = prev.get("mood", [])
    result["mood"] = list(dict.fromkeys(prev_mood + cur_mood))

    # 누적형: taste_context.suppressed_keywords 기반 (부정 발화 + Q7 negative + 명시 배제어 포함)
    prev_suppressed = prev.get("suppressed", [])
    cur_suppressed  = list(taste_context.get("suppressed_keywords") or [])
    result["suppressed"] = list(dict.fromkeys(prev_suppressed + cur_suppressed))

    return result


# ============================================================
# 헬퍼 함수 구현
# ============================================================


def extract_keywords_from_utterance(
    utterance: str,
    current_date_str: str = "",
    messages: Optional[list[dict]] = None,
    accumulated_keywords: Optional[dict] = None,
) -> list[_ExtractedKeyword]:
    """
    LLM으로 사용자 발화에서 핵심 키워드를 추출한다.

    멀티턴 컨텍스트 주입 전략:
    - accumulated_keywords: 이전 턴들의 핵심 키워드를 카테고리별로 요약한 구조화 데이터.
      raw 발화 전체 대신 이것을 시스템 프롬프트에 주입해 노이즈 없이 맥락을 유지한다.
    - messages[-2] (직전 1턴 raw): "거기서", "그곳" 같은 대명사 해석용.
      직전 발화만 넘기므로 오래된 발화("5월 5일" 등)가 키워드로 잘못 추출되지 않는다.

    Args:
        utterance: 사용자 자연어 발화 (현재 턴)
        current_date_str: Asia/Seoul 기준 현재 날짜 문자열
        messages: 누적 대화 히스토리 (직전 1턴 대명사 해석에만 사용)
        accumulated_keywords: 이전 턴들의 카테고리별 핵심 키워드 요약
    """
    system_prompt = _load_prompt("extract_keywords")

    # 날짜 주입
    prefix_parts: list[str] = []
    if current_date_str:
        prefix_parts.append(f"오늘 날짜(Asia/Seoul 기준): {current_date_str}")

    # 누적 키워드 컨텍스트 주입 — raw 발화 대신 구조화된 요약을 넣어 노이즈 차단
    if accumulated_keywords:
        lines: list[str] = ["[이전 대화에서 파악된 사용자 관심사]"]
        if accumulated_keywords.get("location"):
            lines.append(f"  위치: {', '.join(accumulated_keywords['location'])}")
        if accumulated_keywords.get("mood"):
            lines.append(f"  선호 분위기: {', '.join(accumulated_keywords['mood'])}")
        if accumulated_keywords.get("place_type"):
            lines.append(f"  장소 유형: {', '.join(accumulated_keywords['place_type'])}")
        if accumulated_keywords.get("food_type"):
            lines.append(f"  음식 유형: {', '.join(accumulated_keywords['food_type'])}")
        if accumulated_keywords.get("suppressed"):
            lines.append(f"  원하지 않는 것: {', '.join(accumulated_keywords['suppressed'])}")
        lines.append(
            "위 맥락은 참고용입니다.\n"
            "규칙:\n"
            "  1. 현재 발화에 명시적으로 언급된 항목만 키워드로 추출하세요.\n"
            "  2. 위치(location)만 예외 — 현재 발화에 장소가 없으면 이전 위치를 그대로 추출하세요.\n"
            "  3. '거기', '그곳', '거기서' 등 대명사는 이전 위치로 해석하세요.\n"
            "  4. 이전 음식·장소·활동 항목은 현재 발화에 언급되지 않으면 절대 추출하지 마세요."
        )
        prefix_parts.append("\n".join(lines))

    if prefix_parts:
        system_prompt = "\n\n".join(prefix_parts) + "\n\n" + system_prompt

    llm_structured = _get_llm().with_structured_output(_KeywordExtractionResult)

    use_previous_context = _is_contextual_followup(utterance)

    # 직전 1턴은 대명사("거기서") 같은 명시적 이어받기 표현이 있을 때만 전달
    from langchain_core.messages import AIMessage
    lc_messages: list = [SystemMessage(content=system_prompt)]
    if use_previous_context and messages and len(messages) >= 2:
        prev = messages[-2]
        if prev["role"] == "user":
            lc_messages.append(HumanMessage(content=prev["content"]))
        elif prev["role"] == "assistant":
            lc_messages.append(AIMessage(content=prev["content"]))
    lc_messages.append(HumanMessage(content=utterance))

    result: _KeywordExtractionResult = llm_structured.invoke(lc_messages)

    # 검증 범위: 기본은 현재 발화만. 명시적 follow-up일 때만 직전 발화까지 허용한다.
    prev_utterance = (
        messages[-2]["content"]
        if use_previous_context and messages and len(messages) >= 2
        else ""
    )
    validation_context = f"{prev_utterance} {utterance}".strip()
    return _validate_keywords_against_utterance(result.keywords, validation_context)


def check_onboarding_match(
    keywords: list[_ExtractedKeyword],
    onboarding_data: OnboardingData,
) -> bool:
    """
    추출된 키워드를 처리하기에 온보딩 데이터가 충분한지 확인한다.

    판단 기준:
    - tourist 힌트 키워드가 있는데 tourist_spots 온보딩이 비어있으면 → 부족
    - foodie 힌트 키워드가 있는데 foodie_spots 온보딩이 비어있으면 → 부족
    - 그 외는 충분하다고 판단 (추론 가능)

    Args:
        keywords: extract_keywords_from_utterance() 결과
        onboarding_data: 사용자 온보딩 데이터

    Returns:
        bool: True면 충분, False면 추가 질문 필요
    """
    hints = {kw.agent_hint for kw in keywords}

    if "tourist" in hints and not onboarding_data.get("tourist_spots"):
        return False
    if "foodie" in hints and not onboarding_data.get("foodie_spots"):
        return False
    if "event" in hints and not onboarding_data.get("music"):
        # 이벤트 추천도 음악 취향 데이터를 활용하므로 확인
        return False

    return True


def generate_clarification_question(
    keywords: list[_ExtractedKeyword],
    onboarding_data: OnboardingData,
) -> Optional[str]:
    """
    온보딩 데이터 부족 시 추가 질문 1개로 해결 가능한지 판단하고 질문을 생성한다.

    Args:
        keywords: 추출된 키워드 목록
        onboarding_data: 현재 온보딩 데이터

    Returns:
        str: 사용자에게 보낼 질문 텍스트 (추가 질문 필요 시)
        None: 추론으로 충분히 진행 가능할 때
    """
    system_prompt = _load_prompt("generate_clarification")

    user_content = (
        f"키워드: {[kw.keyword for kw in keywords]}\n"
        f"온보딩 데이터:\n"
        f"  - 음악: {onboarding_data.get('music', [])}\n"
        f"  - 관광지: {onboarding_data.get('tourist_spots', [])}\n"
        f"  - 맛집: {onboarding_data.get('foodie_spots', [])}\n"
    )

    response = _get_llm().invoke(
        [SystemMessage(content=system_prompt), HumanMessage(content=user_content)]
    )

    answer = response.content.strip()
    return None if answer in ("없음", "none", "null", "") else answer


def detect_tpo_conflict(
    keywords: list[_ExtractedKeyword],
    onboarding_data: OnboardingData,
) -> bool:
    """
    LLM으로 현재 요청 키워드와 온보딩 음악 취향 간 TPO 충돌을 감지한다.

    충돌 예시:
    - 에너제틱 음악 취향 (EDM, 힙합) + 조용한 장소 요청 (북촌한옥마을) → True
    - 잔잔한 음악 취향 (lo-fi) + 감성 카페 요청 → False

    Args:
        keywords: 추출된 키워드 목록
        onboarding_data: 사용자 온보딩 데이터

    Returns:
        bool: True면 충돌 감지 → 사용자에게 선택지 제시 필요
    """
    current_terms = [
        kw.keyword
        for kw in keywords
        if kw.category in ("mood", "place_type", "activity")
    ]
    if not current_terms:
        return False

    onboarding_terms = (
        onboarding_data.get("music", [])
        + onboarding_data.get("preferred_mood", [])
    )
    current_text = " ".join(current_terms)
    onboarding_text = " ".join(onboarding_terms)

    calm_terms = ("조용", "차분", "잔잔", "한적", "편안", "아늑", "감성", "애틋")
    energetic_terms = (
        "신나는", "활기", "힙합", "EDM", "클럽", "핫플", "북적",
        "시끄", "시크러운", "라운지", "바", "펍", "나이트라이프",
    )

    current_calm = any(term in current_text for term in calm_terms)
    current_energetic = any(term in current_text for term in energetic_terms)
    onboarding_calm = any(term in onboarding_text for term in calm_terms)
    onboarding_energetic = any(term in onboarding_text for term in energetic_terms)

    return (current_calm and onboarding_energetic) or (
        current_energetic and onboarding_calm
    )


def build_conflict_question(
    keywords: list[_ExtractedKeyword],
    onboarding_data: OnboardingData,
) -> str:
    """
    TPO 충돌 감지 시 사용자에게 제시할 선택지 질문을 생성한다.

    Q2 결정: 사용자에게 3가지 선택지 제시
      A. 음악 취향 기준 추천
      B. 현재 요청 분위기 기준 추천
      C. 둘 다 (카테고리 분리 출력)

    Args:
        keywords: 추출된 키워드 목록
        onboarding_data: 사용자 온보딩 데이터

    Returns:
        str: 사용자에게 보낼 선택지 질문 텍스트
    """
    music_list = onboarding_data.get("music", [])
    place_keywords = [
        kw.keyword
        for kw in keywords
        if kw.category in ("place_type", "mood", "location")
    ]

    music_summary = ", ".join(music_list[:2]) if music_list else "음악 취향"
    place_summary = ", ".join(place_keywords[:2]) if place_keywords else "현재 요청"

    return (
        f"평소 즐기시는 음악 분위기({music_summary})와 "
        f"지금 찾으시는 곳({place_summary})의 느낌이 조금 다른데요!\n\n"
        f"어떤 기준으로 추천해드릴까요?\n"
        f"A. 평소 음악 취향 분위기로 추천\n"
        f"B. 지금 원하시는 분위기로 추천\n"
        f"C. 둘 다 보여주기 (음악 분위기 기준 / 장소 분위기 기준 나눠서)"
    )


def build_taste_context(
    extracted_keywords: list[_ExtractedKeyword],
    onboarding_data: OnboardingData,
    previous_turn: Optional[PreviousTurn] = None,
    tpo_choice: Optional[str] = None,
    onboarding_mood_keywords: Optional[list[str]] = None,
) -> dict:
    """
    자연어 발화 키워드 + 온보딩 데이터 + 직전 반응을 통합한 취향 객체를 구성한다.

    가중치 적용 (Q2):
    - 현재 발화 키워드: WEIGHT_CURRENT_UTTERANCE (×2.0)
    - 온보딩 데이터:    WEIGHT_ONBOARDING       (×1.0)

    직전 반응 반영 (Q7):
    - POSITIVE: 직전 키워드 패턴 강화 → boosted_keywords에 추가
    - NEGATIVE: 직전 키워드 억제       → suppressed_keywords에 추가
    - NEUTRAL / NONE: 그대로 진행

    TPO 충돌 선택 반영 (Q2 C 옵션):
    - tpo_choice="C" 일 때 onboarding_mood_keywords와 current_mood_keywords를
      분리해서 반환 → Worker Agent가 두 그룹 출력([🎵 차분] / [🎉 활기])에 활용

    Args:
        extracted_keywords: 현재 발화에서 추출된 키워드 (C 선택 시 온보딩 무드 포함)
        onboarding_data: 사용자 온보딩 데이터
        previous_turn: 직전 턴 반응 정보 (없으면 None)
        tpo_choice: TPO 충돌 선택 결과 ("A" / "B" / "C" / None)
        onboarding_mood_keywords: 온보딩 음악 취향에서 온 무드 키워드 목록
                                  (A·C 선택 시 전달, 그 외 None)

    Returns:
        dict: Worker Agent에 전달할 통합 취향 객체
    """
    # Q7: 직전 반응 반영
    boosted_keywords: list[str] = []
    suppressed_keywords: list[str] = []

    if previous_turn:
        reaction = previous_turn.get("user_reaction", REACTION_NONE)
        last_kws: list[str] = previous_turn.get("last_keywords") or []

        if reaction == REACTION_POSITIVE:
            boosted_keywords = last_kws
        elif reaction == REACTION_NEGATIVE:
            suppressed_keywords = last_kws
        # NEUTRAL → 다양성 증가 (Worker Agent에서 처리)
        # NONE    → 처음부터 재시작, previous 무시

    # 현재 발화 내 부정 키워드 감지 → suppressed_keywords에 추가
    utterance_negative = [
        kw.keyword for kw in extracted_keywords if _is_negative_keyword(kw.keyword)
    ]
    suppressed_keywords = list(set(suppressed_keywords + utterance_negative))

    # 부정 키워드는 current_keywords에서 제외
    positive_keywords = [kw for kw in extracted_keywords if not _is_negative_keyword(kw.keyword)]

    return {
        # 현재 발화 키워드 (×2.0, 부정 표현 제외)
        "current_keywords": [kw.keyword for kw in positive_keywords],
        "current_weight": WEIGHT_CURRENT_UTTERANCE,

        # 온보딩 취향 데이터 (×1.0)
        "preferred_music": onboarding_data.get("music", []),
        "preferred_spots": onboarding_data.get("tourist_spots", []),
        "preferred_food": onboarding_data.get("foodie_spots", []),
        "preferred_mood": onboarding_data.get("preferred_mood", []),
        "companion_type": onboarding_data.get("companion_type"),
        "active_time": onboarding_data.get("active_time"),
        "onboarding_weight": WEIGHT_ONBOARDING,

        # 카테고리별 분류 (Worker Agent 필터링용, 부정 표현 제외)
        "mood_keywords": [
            kw.keyword for kw in positive_keywords if kw.category == "mood"
        ],
        "location_keywords": [
            kw.keyword for kw in positive_keywords if kw.category == "location"
        ],
        "place_type_keywords": [
            kw.keyword for kw in positive_keywords if kw.category == "place_type"
        ],
        "food_type_keywords": [
            kw.keyword for kw in positive_keywords if kw.category == "food_type"
        ],
        "event_type_keywords": [
            kw.keyword for kw in positive_keywords if kw.category == "event_type"
        ],

        # Q7 + 현재 발화 부정 표현: 억제 키워드
        "boosted_keywords": boosted_keywords,
        "suppressed_keywords": suppressed_keywords,

        # TPO 충돌 선택 결과 (A/B/C/None) — Worker Agent 출력 분기용
        "tpo_choice": tpo_choice,

        # C 선택 시 두 그룹 분리 출력을 위한 무드 키워드 분류
        # onboarding_mood_keywords: 온보딩 음악 취향에서 온 무드 (차분한 분위기)
        # current_mood_keywords:    현재 발화에서 온 무드 (활기찬 분위기)
        "onboarding_mood_keywords": list(onboarding_mood_keywords or []),
        "current_mood_keywords": [
            kw.keyword for kw in positive_keywords
            if kw.category == "mood"
            and kw.keyword not in set(onboarding_mood_keywords or [])
        ],

        # 라우팅 근거 (테스트·디버깅용)
        "keyword_routing_detail": [
            {"keyword": kw.keyword, "category": kw.category, "agent_hint": kw.agent_hint}
            for kw in extracted_keywords
        ],
    }


def build_keywords_with_reasons(
    extracted_keywords: list[_ExtractedKeyword],
    onboarding_data: OnboardingData,
    previous_turn: Optional[PreviousTurn] = None,
) -> list[KeywordWithReason]:
    """
    추출된 키워드에 추천 근거를 붙인다 (Q5: 설명 가능성 확보).

    근거 생성 규칙:
    - 온보딩 데이터와 매칭되면  → "온보딩에서 '[항목]' 선택"
    - 직전 긍정 반응과 연관되면 → "지난 추천에서 좋아하셨던 패턴"
    - 위 둘 다 해당 없으면      → "현재 요청 기반"

    Args:
        extracted_keywords: 추출된 키워드 목록
        onboarding_data: 사용자 온보딩 데이터
        previous_turn: 직전 턴 반응 정보

    Returns:
        list[KeywordWithReason]: 키워드 + 근거 묶음 리스트
    """
    # 직전 긍정 반응 키워드 집합
    last_liked: set[str] = set()
    if (
        previous_turn
        and previous_turn.get("user_reaction") == REACTION_POSITIVE
    ):
        last_liked = set(previous_turn.get("last_keywords") or [])

    # 온보딩 전체 항목 flat list (부분 문자열 매칭용)
    onboarding_flat: list[str] = (
        onboarding_data.get("music", [])
        + onboarding_data.get("tourist_spots", [])
        + onboarding_data.get("foodie_spots", [])
        + onboarding_data.get("preferred_mood", [])
    )

    result: list[KeywordWithReason] = []

    for kw in extracted_keywords:
        reasons: list[str] = []

        # 온보딩 매칭 (위치 꾸밈말 정규화 + 광역 지명 제외)
        matched_ob = _match_onboarding(kw.keyword, onboarding_flat)
        if matched_ob:
            reasons.append(f"온보딩에서 '{matched_ob}' 선택")

        # 직전 긍정 반응 매칭
        if kw.keyword in last_liked:
            reasons.append("지난 추천에서 좋아하셨던 패턴")

        # 근거 없으면 현재 발화 기반
        if not reasons:
            reasons.append("현재 요청 기반")

        result.append(
            KeywordWithReason(keyword=kw.keyword, reason=" + ".join(reasons))
        )

    return result


def decide_target_agents(extracted_keywords: list[_ExtractedKeyword]) -> list[str]:
    """
    추출된 키워드의 agent_hint를 기반으로 라우팅할 에이전트를 결정한다.

    규칙: 1표라도 받은 에이전트는 모두 포함한다.
    - 복합 의도 발화("구경하고 맛집도 추천해줘")에서 득표수 과반 로직은
      의도적으로 선택된 에이전트를 누락시키는 부작용이 있으므로 사용하지 않는다.
    - 투표가 전혀 없으면 fallback으로 전체 포함

    Args:
        extracted_keywords: 추출된 키워드 목록

    Returns:
        list[str]: 라우팅할 에이전트 이름 목록 (tourist / foodie / event)
    """
    votes = _vote_agents(extracted_keywords)
    total = sum(votes.values())

    if total == 0:
        return [AGENT_TOURIST, AGENT_FOODIE, AGENT_EVENT]

    # 1표 이상 받은 에이전트 모두 포함
    voted = [a for a, c in votes.items() if c > 0]
    return voted if voted else [AGENT_TOURIST, AGENT_FOODIE, AGENT_EVENT]


# ============================================================
# 충돌/추가질문 해소 후 이어서 처리
# ============================================================


def continue_after_clarification(
    pending_state: KDiveState,
    user_choice: str,
) -> KDiveState:
    """
    사용자가 되물음(A/B/C 선택 또는 추가 답변)에 응답한 뒤 처리를 이어간다.

    TPO 충돌(A/B/C) 처리:
      A → 온보딩 음악 취향 기준으로 키워드 재구성
      B → 현재 요청 키워드 그대로 사용
      C → 두 기준 모두 포함해서 처리

    Args:
        pending_state: 충돌/추가질문 감지 시 반환됐던 state
        user_choice: 사용자가 입력한 답변 (A / B / C 또는 자유 텍스트)

    Returns:
        KDiveState: 라우팅·취향 객체가 채워진 최종 state
    """
    state = dict(pending_state)
    state["needs_user_clarification"] = False
    state["has_tpo_conflict"] = False

    previous_turn: Optional[PreviousTurn] = state.get("previous_turn")
    onboarding_data: OnboardingData = state["onboarding_data"]

    clarification_type = state.pop("clarification_type", "tpo_conflict")

    # ── 과거 날짜 경고 응답 처리 ──
    # 사용자가 "네/현재 기준으로" → 원래 발화 그대로 재처리 (current_datetime이 이미 state에 있음)
    # 사용자가 새 날짜/다른 답변 → 해당 입력을 새 발화로 재처리
    if clarification_type == "past_date":
        original_utterance = state["user_utterance"]
        _YES_REPLIES = ("네", "응", "예", "그래", "현재", "맞아", "ok", "yes", "ㅇㅇ", "ㅇ")

        if any(user_choice.strip().lower().startswith(y) for y in _YES_REPLIES):
            # 현재 날짜 기준으로 진행 — 날짜 부분만 제거하고 원래 발화 재처리
            new_utterance = _DATE_PATTERN.sub("", original_utterance).strip()
        else:
            # 사용자 응답에 새 날짜가 있으면 원래 발화의 날짜를 교체
            new_date_match = _DATE_PATTERN.search(user_choice)
            if new_date_match:
                new_date_str = new_date_match.group(0)  # 예: "5월 20일"
                new_utterance = _DATE_PATTERN.sub(new_date_str, original_utterance, count=1)
            else:
                # 날짜 없이 자유 텍스트로 답한 경우 — 원래 발화를 날짜 없이 재처리
                new_utterance = _DATE_PATTERN.sub("", original_utterance).strip()

        fresh_state: KDiveState = {
            "user_utterance": new_utterance,
            "onboarding_data": state["onboarding_data"],
            "messages": state.get("messages") or [],
            "accumulated_keywords": state.get("accumulated_keywords", {}),
        }
        if previous_turn is not None:
            fresh_state["previous_turn"] = previous_turn
        return supervisor_intake(fresh_state)

    # ── 범위 밖(수도권 외) 안내 응답 → 사용자의 새 입력을 새 발화로 처리 ──
    if clarification_type == "out_of_scope":
        fresh_state: KDiveState = {
            "user_utterance": user_choice,
            "onboarding_data": onboarding_data,
            "messages": state.get("messages") or [],
            "accumulated_keywords": state.get("accumulated_keywords", {}),
        }
        if previous_turn is not None:
            fresh_state["previous_turn"] = previous_turn
        # 직전 범위 밖 요청에서 보관해둔 키워드를 새 발화에 이어붙인다
        carried = state.get("_carried_keywords")
        if carried:
            fresh_state["_carried_keywords"] = carried
        return supervisor_intake(fresh_state)

    # _pending_keywords 에서 키워드 복원
    raw_keywords: list[dict] = state.pop("_pending_keywords", [])
    extracted_keywords = [
        _ExtractedKeyword(
            keyword=k["keyword"],
            category=k["category"],
            agent_hint=k["agent_hint"],
            is_past_action=k.get("is_past_action", False),
        )
        for k in raw_keywords
    ]

    # ── 라우팅 애매 질문 응답 처리 (1/2/3 선택) ──
    if clarification_type == "routing":
        target_agents = _parse_routing_choice(user_choice)
        state["target_agents"] = target_agents
        state["agent_taste_contexts"] = build_agent_taste_contexts(
            extracted_keywords=extracted_keywords,
            target_agents=target_agents,
            onboarding_data=onboarding_data,
            previous_turn=previous_turn,
            base_taste_context=state.get("taste_context") or {},
        )
        # taste_context·keywords_with_reasons 는 이미 intake에서 저장됨
        return state

    # ── TPO 충돌 응답 처리 (A/B/C) ──
    choice = _normalize_conflict_choice(user_choice)
    onboarding_mood_list: list[str] = onboarding_data.get("music", [])

    # 선택별로 라우팅용 키워드와 컨텍스트용 키워드를 분리한다.
    #
    # A: 온보딩 음악 취향 기준
    #    - 라우팅·컨텍스트 모두 location + 음악 무드 키워드만 사용
    # B: 현재 요청 기준
    #    - 라우팅·컨텍스트 모두 원본 발화 키워드 그대로
    # C: 둘 다
    #    - 라우팅:    현재 발화 키워드만 사용 (음악 무드 미포함)
    #    - 컨텍스트:  현재 발화 + 음악 무드 키워드 합산
    #    → Worker Agent가 두 그룹([🎵 차분] / [🎉 활기])으로 나눠 출력

    if choice == "A":
        music_mood_keywords = [
            _ExtractedKeyword(keyword=m, category="mood", agent_hint="any")
            for m in onboarding_mood_list
        ]
        keywords_for_routing = (
            [kw for kw in extracted_keywords if kw.category != "mood"]
            + music_mood_keywords
        )
        keywords_for_context = keywords_for_routing
        context_onboarding_mood = onboarding_mood_list

    elif choice == "C":
        music_mood_keywords = [
            _ExtractedKeyword(keyword=m, category="mood", agent_hint="any")
            for m in onboarding_mood_list
        ]
        keywords_for_routing = extracted_keywords          # 라우팅: 현재 키워드만
        keywords_for_context = extracted_keywords + music_mood_keywords  # 컨텍스트: 합산
        context_onboarding_mood = onboarding_mood_list

    else:  # B: 현재 요청 기준 → 그대로
        keywords_for_routing = extracted_keywords
        keywords_for_context = extracted_keywords
        context_onboarding_mood = []

    # 4. 취향 객체 구성
    keywords_with_reasons = build_keywords_with_reasons(
        extracted_keywords=keywords_for_context,
        onboarding_data=onboarding_data,
        previous_turn=previous_turn,
    )
    taste_context = build_taste_context(
        extracted_keywords=keywords_for_context,
        onboarding_data=onboarding_data,
        previous_turn=previous_turn,
        tpo_choice=choice,
        onboarding_mood_keywords=context_onboarding_mood,
    )
    taste_context["allow_onboarding_anchors"] = _should_allow_onboarding_anchors(
        state["user_utterance"], keywords_for_routing
    )
    _apply_deterministic_taste_boost(taste_context, state["user_utterance"])
    state["accumulated_keywords"] = _merge_accumulated_keywords(
        current_keywords=keywords_for_context,
        taste_context=taste_context,
        previous=state.get("accumulated_keywords"),
    )
    taste_context["conversation_context"] = _build_conversation_context(
        messages=state.get("messages") or [],
        accumulated_keywords=state.get("accumulated_keywords"),
        previous_turn=previous_turn,
    )

    # 5. 라우팅 결정 (C는 현재 키워드만, A는 음악 무드 키워드 기준)
    target_agents = decide_target_agents(extracted_keywords=keywords_for_routing)
    state["agent_taste_contexts"] = build_agent_taste_contexts(
        extracted_keywords=keywords_for_context,
        target_agents=target_agents,
        onboarding_data=onboarding_data,
        previous_turn=previous_turn,
        base_taste_context=taste_context,
        tpo_choice=choice,
        onboarding_mood_keywords=context_onboarding_mood,
    )

    state["keywords_with_reasons"] = keywords_with_reasons
    state["taste_context"] = taste_context
    state["target_agents"] = target_agents

    return state


# ============================================================
# 내부 유틸 함수
# ============================================================

# 원문 존재 여부를 검증할 카테고리 — LLM이 변형·축약하면 안 되는 사실형 키워드
_FACTUAL_CATEGORIES = frozenset({"place_type", "food_type", "location", "event_type"})
_VALID_AGENT_HINTS = frozenset({"tourist", "foodie", "event", "any"})


def _validate_keywords_against_utterance(
    keywords: list[_ExtractedKeyword],
    utterance: str,
) -> list[_ExtractedKeyword]:
    """
    LLM이 추출한 키워드 중 원문에 없는 사실형 키워드를 제거한다.

    'place_type', 'food_type', 'location', 'event_type' 카테고리에 한해,
    키워드(공백 제거)가 원문(공백 제거)의 부분 문자열인지 확인한다.
    없으면 LLM이 단어를 잘라냈거나 만들어낸 것으로 판단해 제거한다.

    mood · activity · other 등은 LLM이 정규화하는 것이 의도된 동작이므로 그대로 유지.

    location 카테고리 특별 처리:
    - 원문 검증 통과 여부와 무관하게 꾸밈말(근처/주변 등)을 제거한 정규화 형태로 저장한다.
      예) "혜화역 근처" → "혜화역", "강남 주변" → "강남"
    - 원문에 없는 키워드도 꾸밈말 제거 후 2자 이상이면 재검증해 통과 시 저장한다.
    """
    utterance_flat = utterance.replace(" ", "")
    validated = []
    for kw in keywords:
        if kw.agent_hint not in _VALID_AGENT_HINTS:
            kw = _ExtractedKeyword(
                keyword=kw.keyword,
                category=kw.category,
                agent_hint="any",
                is_past_action=kw.is_past_action,
            )
        if kw.category in _FACTUAL_CATEGORIES:
            kw_flat = kw.keyword.replace(" ", "")
            if len(kw_flat) < 2:
                continue
            if kw_flat and kw_flat not in utterance_flat:
                # location 카테고리: 꾸밈말 제거 후 재검증
                if kw.category == "location":
                    norm = _normalize_for_matching(kw.keyword)
                    norm_flat = norm.replace(" ", "")
                    if len(norm_flat) >= 2 and norm_flat in utterance_flat:
                        validated.append(
                            _ExtractedKeyword(
                                keyword=norm,
                                category=kw.category,
                                agent_hint=kw.agent_hint,
                                is_past_action=kw.is_past_action,
                            )
                        )
                continue  # 원문에 없는 키워드(정규화 후 추가된 경우 포함) — 원본 스킵
            # 원문 검증 통과 — location은 꾸밈말 제거 후 저장
            if kw.category == "location":
                norm = _normalize_for_matching(kw.keyword)
                if norm != kw.keyword:
                    kw = _ExtractedKeyword(
                        keyword=norm,
                        category=kw.category,
                        agent_hint=kw.agent_hint,
                        is_past_action=kw.is_past_action,
                    )
        validated.append(kw)
    return validated


def _detect_travel_phase(utterance: str) -> TravelPhase:
    """
    사용자 발화를 보고 여행 단계를 감지한다.

    판단 기준:
    - pre_trip    : "다음 주에", "여행 갈 건데", "계획 중" 등 미래형 표현
    - during_trip : "지금 여기", "현재 위치", "지금 있어" 등 현재 진행형 표현
    - unknown     : 판단 불가

    Args:
        utterance: 사용자 자연어 발화

    Returns:
        TravelPhase: "pre_trip" | "during_trip" | "unknown"
    """
    system_prompt = (
        "사용자 발화를 보고 여행 단계를 판단하세요.\n\n"
        "- 여행을 계획 중이거나 앞으로 갈 예정이면 'pre_trip'\n"
        "- 현재 여행 중이거나 지금 현장에 있으면 'during_trip'\n"
        "- 판단하기 어려우면 'unknown'\n\n"
        "travel_phase 필드에 정확히 'pre_trip', 'during_trip', 'unknown' 중 하나만 반환하세요."
    )
    llm_structured = _get_llm().with_structured_output(_TravelPhaseResult)
    result: _TravelPhaseResult = llm_structured.invoke(
        [SystemMessage(content=system_prompt), HumanMessage(content=utterance)]
    )
    phase = result.travel_phase
    if phase in ("pre_trip", "during_trip", "unknown"):
        return phase  # type: ignore[return-value]
    return "unknown"


_DATE_PATTERN = re.compile(r"(\d{1,2})월\s*(\d{1,2})일")


def _detect_past_date(utterance: str, today: date) -> tuple:
    """
    발화에서 'N월 N일' 패턴을 정규식으로 찾아 오늘보다 과거인지 판단한다.
    연도가 생략된 경우 오늘 날짜의 연도로 가정한다.

    Args:
        utterance: 사용자 자연어 발화
        today: Asia/Seoul 기준 오늘 날짜 (date 객체)

    Returns:
        (is_past: bool, detected_date: str)
    """
    match = _DATE_PATTERN.search(utterance)
    if not match:
        return False, ""

    month, day = int(match.group(1)), int(match.group(2))
    try:
        mentioned = date(today.year, month, day)
    except ValueError:
        return False, ""

    if mentioned < today:
        return True, f"{month}월 {day}일"
    return False, ""


def _normalize_conflict_choice(user_input: str) -> str:
    """
    사용자의 자유 텍스트 응답을 A / B / C 중 하나로 정규화한다.

    인식 규칙:
      A → "A", "음악", "평소", "music"
      B → "B", "지금", "현재", "요청", "current"
      C → "C", "둘", "both", "다", "모두", "전부", "같이", "함께"
    매칭 안 되면 기본값 B 반환.
    """
    text = user_input.strip().upper()

    # 정확한 단일 알파벳 매칭 우선
    if text in ("A", "B", "C"):
        return text

    text_lower = user_input.strip().lower()

    c_keywords = ("둘", "both", "다 보여", "모두", "전부", "같이", "함께", "둘다", "둘 다")
    a_keywords = ("음악", "평소", "music")
    b_keywords = ("지금", "현재", "요청", "current")

    if any(k in text_lower for k in c_keywords):
        return "C"
    if any(k in text_lower for k in a_keywords):
        return "A"
    if any(k in text_lower for k in b_keywords):
        return "B"

    return "B"  # 기본값: 현재 요청 기준


def _is_negative_keyword(keyword: str) -> bool:
    """키워드가 부정/거부 표현인지 판단한다."""
    return any(pattern in keyword for pattern in _NEGATIVE_PATTERNS)


def _scan_tourist_intent_terms(utterance: str) -> list[str]:
    """발화 원문에서 tourist 의도 어휘를 결정적으로 잡는다.

    LLM 키워드 추출이 행동 동사를 일관되게 tourist 로 라우팅하지 못해도
    동일한 어휘를 detect 해서 가상 키워드로 라우팅 투표에 합류시킨다.
    """
    return [term for term in _TOURIST_INTENT_TERMS if term in utterance]


def _detect_explicit_exclusions(utterance: str) -> list[str]:
    """발화에서 명시적 배제 의도를 결정적으로 감지한다.

    규칙:
    - 발화에 부정 표현(_NEGATIVE_PATTERNS) 이 있고 _EXPLICIT_EXCLUDE_TERMS 중
      하나가 등장하면 그 항목을 suppress 대상으로 본다.
    - "로컬/동네/개인/독립/숨은" 같은 표현은 "체인 배제" 의 함의로 보고
      "체인" 을 자동으로 suppress 한다 (dummy_server 정책과 일치).
    """
    suppressed: list[str] = []
    has_negation = any(p in utterance for p in _NEGATIVE_PATTERNS)
    if has_negation:
        for term in _EXPLICIT_EXCLUDE_TERMS:
            if term in utterance:
                suppressed.append(term)
    if any(term in utterance for term in _LOCAL_INTENT_TERMS):
        suppressed.append("체인")
    return list(dict.fromkeys(suppressed))


def _apply_deterministic_taste_boost(taste_context: dict, utterance: str) -> None:
    """발화 원문 기반 결정적 보강을 taste_context 에 in-place 로 합친다.

    현재는 명시 배제 어휘를 suppressed_keywords 에 union 한다.
    tourist 의도 보강은 extracted_keywords 단에서 가상 키워드로 들어가므로
    여기에 포함하지 않는다.
    """
    explicit_exclusions = _detect_explicit_exclusions(utterance)
    if not explicit_exclusions:
        return
    current = list(taste_context.get("suppressed_keywords") or [])
    for term in explicit_exclusions:
        if term not in current:
            current.append(term)
    taste_context["suppressed_keywords"] = current


def _should_allow_onboarding_anchors(
    utterance: str,
    extracted_keywords: list["_ExtractedKeyword"],
) -> bool:
    """
    온보딩 liked_places 좌표를 자동 anchor로 사용해도 되는지 결정한다.

    원칙: 사용자가 발화에 명시한 지역(location 키워드)을 온보딩 좌표가 덮어쓰면 안 된다.
    - 발화에 location 키워드가 있으면 False (사용자 의도 우선)
    - location 키워드가 없으면 True (발화에 단서가 없을 때만 온보딩 좌표 활용)

    "혜화역 근처"처럼 인접 표현이 있어도 anchor는 발화 location 기준이지
    온보딩 location 기준이 아니므로 마찬가지로 False 처리한다.
    좌표 변환은 worker가 발화 location을 가지고 별도로 수행해야 한다.
    """
    return not any(kw.category == "location" for kw in extracted_keywords)


def _normalize_for_matching(keyword: str) -> str:
    """온보딩 매칭 전에 키워드에서 위치 꾸밈말("근처" 등)을 떼어 핵심 표현만 남긴다."""
    norm = keyword.strip()
    for modifier in _LOCATION_MODIFIERS:
        if norm.endswith(modifier) and len(norm) > len(modifier):
            norm = norm[: -len(modifier)].strip()
    return norm


def _match_onboarding(keyword: str, onboarding_flat: list[str]) -> Optional[str]:
    """
    키워드를 정규화한 뒤 온보딩 항목과 부분 문자열 매칭한다.

    - "남산 근처" → "남산" 으로 정규화 후 "남산서울타워" 와 매칭됨
    - "서울" 같은 광역 지명은 특정 장소명의 근거가 될 수 없으므로 매칭 제외

    매칭되면 해당 온보딩 항목 문자열을, 매칭 실패 시 None 을 반환한다.
    """
    norm = _normalize_for_matching(keyword)
    if not norm or norm in _GENERIC_LOCATIONS:
        return None
    for ob in onboarding_flat:
        if norm in ob or ob in norm:
            return ob
    return None


def _vote_agents(extracted_keywords: list[_ExtractedKeyword]) -> dict[str, int]:
    """
    위치(location)·무드(mood) 키워드를 제외하고 에이전트별 투표수를 계산한다.

    - mood 키워드는 필터링 전용이므로 라우팅 투표에서 제외한다.
    - place_type이고 agent_hint가 "any"인 키워드(클럽, 라이브 바 등)는
      장소 검색이므로 tourist 로 카운트한다.
    """
    votes: dict[str, int] = {AGENT_TOURIST: 0, AGENT_FOODIE: 0, AGENT_EVENT: 0}
    for kw in extracted_keywords:
        if kw.is_past_action:
            continue  # 과거 완료 행동은 라우팅 투표에서 제외 (배경 맥락 전용)
        if kw.category in ("location", "mood"):
            continue  # 위치·무드는 라우팅 투표에서 제외 (필터링 전용)
        if kw.category == "place_type" and kw.agent_hint == "any":
            votes[AGENT_TOURIST] += 1  # 장소 타입 "any"는 tourist로 귀속
            continue
        if kw.agent_hint in votes:
            votes[kw.agent_hint] += 1
    return votes


def is_routing_ambiguous(extracted_keywords: list[_ExtractedKeyword]) -> bool:
    """
    라우팅 결정이 애매한지 판단한다.

    애매한 경우 (질문 필요):
    - 위치·무드를 제외하고 특정 에이전트 투표가 하나도 없는 경우 (전부 "any")
      예) "서울에서 뭔가 특별한 거 하고 싶어"

    애매하지 않은 경우 (복합 의도 → 투표받은 에이전트 모두 라우팅):
    - 복수 에이전트가 각각 1표 이상 받은 경우
      예) "구경하고 초밥도 먹고 싶어" → tourist 1표 + foodie 1표 → 둘 다 라우팅
    """
    votes = _vote_agents(extracted_keywords)
    total = sum(votes.values())
    return total == 0  # 특정 에이전트 힌트가 전혀 없을 때만 애매함


def detect_region_scope(utterance: str) -> tuple[list[str], list[str]]:
    """
    발화 원문을 결정적으로 스캔해 (수도권 밖 지명, 수도권 지명) 을 반환한다.

    LLM 키워드 추출이 지명을 누락해도 동작하도록, 추출 결과가 아니라
    발화 텍스트 자체를 검사한다.
    """
    return _scan_regions(utterance, _OUT_OF_SCOPE_REGIONS), _scan_regions(
        utterance, _CAPITAL_AREA_REGIONS
    )


def _scan_regions(utterance: str, regions: frozenset) -> list[str]:
    """발화에 등장하는 지명을 찾되, 다른 매칭의 부분 문자열인 것은 제외한다.

    예) "제주도" 발화는 "제주"·"제주도" 둘 다 잡히는데, 더 구체적인 "제주도"만 남긴다.
    """
    matched = [r for r in regions if r in utterance]
    maximal = [
        r for r in matched
        if not any(r != other and r in other for other in matched)
    ]
    return sorted(maximal)


def _build_out_of_scope_question(out_of_scope_locations: list[str]) -> str:
    """서비스 범위(수도권) 밖 지역 요청 시 사용자를 수도권으로 유도하는 안내 메시지를 생성한다."""
    location_text = ", ".join(out_of_scope_locations)
    return (
        f"앗, {location_text} 쪽은 아직 추천을 도와드리기 어려워요.\n"
        f"지금은 서울·경기·인천 수도권 지역만 추천해드리고 있어요.\n\n"
        f"수도권에서 가보고 싶은 곳이나 궁금한 지역이 있으실까요?"
    )


def _build_routing_question() -> str:
    """라우팅 애매 시 사용자에게 제시할 에이전트 선택 질문을 생성한다."""
    return (
        "어떤 걸 찾고 계신가요? (번호나 이름으로 답해주세요)\n\n"
        "1. 관광 명소 (공원, 한옥마을, 산책로, 뷰포인트 등)\n"
        "2. 맛집 · 카페\n"
        "3. 전시 · 팝업 · 이벤트\n\n"
        "복수 선택도 가능해요. 예) \"1, 2\" 또는 \"관광이랑 맛집 둘 다\""
    )


def _parse_routing_choice(user_input: str) -> list[str]:
    """
    사용자의 에이전트 선택 응답을 에이전트 목록으로 변환한다.

    인식 규칙:
      tourist → "1", "관광", "명소", "산책", "공원"
      foodie  → "2", "맛집", "카페", "음식", "먹"
      event   → "3", "전시", "팝업", "이벤트", "공연"
    매칭 없으면 전체 반환.
    """
    text = user_input.lower()
    result: list[str] = []

    if any(k in text for k in ("1", "관광", "명소", "산책", "공원", "tourist")):
        result.append(AGENT_TOURIST)
    if any(k in text for k in ("2", "맛집", "카페", "음식", "먹", "foodie")):
        result.append(AGENT_FOODIE)
    if any(k in text for k in ("3", "전시", "팝업", "이벤트", "공연", "event")):
        result.append(AGENT_EVENT)

    return result if result else [AGENT_TOURIST, AGENT_FOODIE, AGENT_EVENT]


def _load_prompt(prompt_name: str) -> str:
    """prompts/ 폴더에서 프롬프트 텍스트를 로드한다."""
    base_dir = os.path.dirname(__file__)
    prompt_path = os.path.join(base_dir, "prompts", f"{prompt_name}.txt")
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read().strip()


def _format_tpo_input(
    keywords: list[_ExtractedKeyword],
    onboarding_data: OnboardingData,
) -> str:
    """TPO 충돌 감지 LLM 입력 텍스트를 구성한다."""
    mood_kws = [kw.keyword for kw in keywords if kw.category == "mood"]
    all_kws = [kw.keyword for kw in keywords]

    return (
        f"음악 취향 (온보딩): {onboarding_data.get('music', [])}\n"
        f"장소 취향 (온보딩): {onboarding_data.get('tourist_spots', [])}\n"
        f"현재 요청 전체 키워드: {all_kws}\n"
        f"현재 요청 분위기 키워드: {mood_kws}\n"
    )
