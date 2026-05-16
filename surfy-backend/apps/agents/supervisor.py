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
from typing import Optional

from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from .state import (
    KDiveState,
    OnboardingData,
    KeywordWithReason,
    PreviousTurn,
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

# 위치 키워드 정규화용 — 온보딩 매칭 전에 떼어낼 위치 꾸밈말
# "남산 근처" → "남산" 으로 만들어 "남산서울타워" 와 매칭되게 한다.
_LOCATION_MODIFIERS = ("근처", "주변", "근방", "인근", "일대", "쪽")

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
    "한남동", "을지로", "익선동", "남산", "한강",
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


class _TpoConflictResult(BaseModel):
    has_conflict: bool = Field(description="음악 취향과 현재 요청 분위기 간 충돌 여부")
    conflict_summary: str = Field(description="충돌 이유 (충돌 없으면 빈 문자열)")


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

    # ----- 1. 키워드 추출 (LLM) -----
    extracted_keywords = extract_keywords_from_utterance(
        utterance=state["user_utterance"]
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
    for region in capital_area_regions:
        if not any(region in kw.keyword for kw in extracted_keywords):
            extracted_keywords.append(
                _ExtractedKeyword(
                    keyword=region, category="location", agent_hint="any"
                )
            )

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

    # ----- 결과를 State에 담기 -----
    state["keywords_with_reasons"] = keywords_with_reasons
    state["taste_context"] = taste_context
    state["target_agents"] = target_agents
    state["needs_user_clarification"] = False

    return state


# ============================================================
# 헬퍼 함수 구현
# ============================================================


def extract_keywords_from_utterance(utterance: str) -> list[_ExtractedKeyword]:
    """
    LLM으로 사용자 발화에서 핵심 키워드를 추출한다.

    각 키워드에는 category(place_type / mood / location 등)와
    agent_hint(어떤 에이전트 담당인지)가 붙는다.

    Args:
        utterance: 사용자 자연어 발화

    Returns:
        list[_ExtractedKeyword]: 카테고리·에이전트 힌트가 붙은 키워드 목록
    """
    system_prompt = _load_prompt("extract_keywords")
    llm_structured = _get_llm().with_structured_output(_KeywordExtractionResult)

    result: _KeywordExtractionResult = llm_structured.invoke(
        [SystemMessage(content=system_prompt), HumanMessage(content=utterance)]
    )
    return result.keywords


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
    system_prompt = _load_prompt("detect_tpo_conflict")
    user_content = _format_tpo_input(keywords, onboarding_data)

    llm_structured = _get_llm().with_structured_output(_TpoConflictResult)
    result: _TpoConflictResult = llm_structured.invoke(
        [SystemMessage(content=system_prompt), HumanMessage(content=user_content)]
    )
    return result.has_conflict


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

    # ── 범위 밖(수도권 외) 안내 응답 → 사용자의 새 입력을 새 발화로 처리 ──
    if clarification_type == "out_of_scope":
        fresh_state: KDiveState = {
            "user_utterance": user_choice,
            "onboarding_data": onboarding_data,
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
            [kw for kw in extracted_keywords if kw.category == "location"]
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

    # 5. 라우팅 결정 (C는 현재 키워드만, A는 음악 무드 키워드 기준)
    target_agents = decide_target_agents(extracted_keywords=keywords_for_routing)

    state["keywords_with_reasons"] = keywords_with_reasons
    state["taste_context"] = taste_context
    state["target_agents"] = target_agents

    return state


# ============================================================
# 내부 유틸 함수
# ============================================================


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
