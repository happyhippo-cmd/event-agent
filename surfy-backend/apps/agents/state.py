"""
K-Dive Agent State 정의
LangGraph 노드 간에 공유되는 전체 상태 스키마
"""

from typing import Optional, Literal
from typing_extensions import TypedDict, NotRequired

# 여행 단계 타입
# "pre_trip"    : 여행 전 (계획 중)
# "during_trip" : 여행 중 (현재 이동/탐색 중)
# "unknown"     : 판단 불가
TravelPhase = Literal["pre_trip", "during_trip", "unknown"]

# ============================================================
# 상수 정의
# ============================================================

# Agent 라우팅 옵션
AGENT_TOURIST = "tourist"
AGENT_FOODIE = "foodie"
AGENT_RESTAURANT = "restaurant"
AGENT_EVENT = "event"

# 가중치 (Q2 가중치 룰)
WEIGHT_CURRENT_UTTERANCE = 2.0   # 현재 발화 (지금의 의도)
WEIGHT_EXPLICIT_DISLIKE = 1.5    # 명시적 싫어요
WEIGHT_RECENT_BEHAVIOR = 1.2     # 최근 행동 (클릭, 좋아요)
WEIGHT_ONBOARDING = 1.0          # 온보딩 데이터 (음악/장소 선택)

# 사용자 반응 타입 (Q7)
REACTION_POSITIVE = "positive"   # "좋네!", "이거 갈래!"
REACTION_NEUTRAL = "neutral"     # 반응 없음
REACTION_NEGATIVE = "negative"   # "별로", "다른 거"
REACTION_NONE = "none"           # 무응답 (오래 대화 없음)

# ============================================================
# TypedDict 정의
# ============================================================


class OnboardingData(TypedDict):
    """온보딩에서 받은 사용자 취향 데이터 (필수 9개 + 선택)"""
    music: list[str]          # 필수 3개 + 추가 선택 (ex. ["lo-fi", "어쿠스틱", "인디"])
    tourist_spots: list[str]  # 필수 3개 + 추가 선택 (ex. ["북촌한옥마을", "경복궁"])
    foodie_spots: list[str]   # 필수 3개 + 추가 선택 (ex. ["홍대 카페거리", "광장시장"])

    # 선택 데이터 (있으면 풍부하게 활용)
    preferred_mood: NotRequired[list[str]]   # ex. ["아늑한", "조용한", "감성적인"]
    companion_type: NotRequired[str]         # ex. "혼자" | "커플" | "친구" | "가족"
    active_time: NotRequired[str]            # ex. "아침" | "낮" | "저녁" | "밤"


class TpoContext(TypedDict):
    """
    TPO(Time/Place/Occasion) 분리 저장 구조 (Q2)
    음악을 들을 때의 무드와 실제로 놀러 갈 때의 무드를 분리해서 저장
    """
    music_listening_mood: list[str]  # 음악 들을 때 선호 분위기 (ex. ["잔잔한", "감성적인"])
    going_out_mood: list[str]        # 놀러 갈 때 선호 분위기 (ex. ["활기찬", "신나는"])


class TasteContext(TypedDict):
    """
    Supervisor → Worker Agent 전달 취향 객체
    supervisor.py의 build_taste_context() 반환값과 1:1 대응
    """
    # ── 현재 발화 키워드 (가중치 ×2.0) ──
    current_keywords: list[str]        # 발화 전체 키워드 (부정 표현 제외)
    current_weight: float              # 현재 발화 가중치 (고정값 2.0)

    # ── 카테고리별 분류 (Worker 필터링용) ──
    mood_keywords: list[str]           # category=mood  (ex. ["조용한", "감성적인"])
    location_keywords: list[str]       # category=location  (ex. ["홍대", "성수"])
    place_type_keywords: list[str]     # category=place_type  (ex. ["카페", "공원"])
    food_type_keywords: list[str]      # category=food_type  (ex. ["초밥", "디저트"])
    event_type_keywords: list[str]     # category=event_type  (ex. ["팝업스토어"])

    # ── 온보딩 취향 (가중치 ×1.0) ──
    preferred_music: list[str]         # ex. ["lo-fi", "어쿠스틱"]
    preferred_spots: list[str]         # ex. ["북촌한옥마을", "남산서울타워"]
    preferred_food: list[str]          # ex. ["초밥집", "화덕피자집"]
    preferred_mood: list[str]          # ex. ["애틋한", "청량한"]
    companion_type: NotRequired[str]   # ex. "혼자" | "커플" | "친구" | "가족"
    active_time: NotRequired[str]      # ex. "아침" | "낮" | "저녁" | "밤"
    onboarding_weight: float           # 온보딩 가중치 (고정값 1.0)

    # ── Q7: 이전 턴 반응 반영 ──
    boosted_keywords: list[str]        # 직전 긍정 반응 키워드 → 유사 결과 강화
    suppressed_keywords: list[str]     # 직전 부정 반응 + 발화 내 "말고" 표현 → 해당 결과 제외

    # ── TPO 충돌 선택 (A/B/C) ──
    tpo_choice: NotRequired[str]              # "A" | "B" | "C" | None
    onboarding_mood_keywords: list[str]       # C 선택 시: 온보딩 음악 기준 무드
    current_mood_keywords: list[str]          # C 선택 시: 현재 발화 기준 무드

    # ── Worker 동작 제어 ──
    allow_onboarding_anchors: bool     # False면 온보딩 장소 좌표로 검색 반경 설정 안 함
                                       # (사용자가 발화에 지역을 명시했을 때 False)

    # ── 디버깅/설명용 ──
    keyword_routing_detail: list[dict] # 키워드별 category·agent_hint 원본 (로그용)
    conversation_context: NotRequired[dict]  # 최근 raw 대화 + 누적 키워드 요약


class KeywordWithReason(TypedDict):
    """
    키워드 + 근거 묶음 (Q5: 설명 가능성 확보)
    Curation Agent에 전달되어 "왜 이걸 추천했는지" 설명 생성에 사용
    """
    keyword: str    # ex. "조용한 분위기"
    reason: str     # ex. "lo-fi 음악 선택 + 북촌한옥마을 좋아요"


class PreviousTurn(TypedDict):
    """
    직전 턴 정보 (Q7: 이전 턴 만족도 자기 평가)
    다음 라우팅·추천 품질에 반영
    """
    user_reaction: Literal["positive", "neutral", "negative", "none"]
    last_recommendation: Optional[list[str]]  # 직전에 추천한 장소/음식 목록
    last_keywords: Optional[list[str]]        # 직전 추천에 사용된 키워드


class KDiveState(TypedDict):
    """
    Supervisor ~ Worker Agent 간에 공유되는 전체 상태

    흐름:
      사용자 입력 → Supervisor(intake) → Worker Agents (병렬)
                  → Supervisor(merge/integrator) → 최종 응답
    """
    # ===== 입력 (매 턴 필수) =====
    user_utterance: str                           # 사용자 자연어 발화
    onboarding_data: OnboardingData               # 온보딩 취향 데이터
    previous_turn: NotRequired[PreviousTurn]      # 직전 턴 정보 (첫 턴엔 없음)

    # ===== 대화 히스토리 (멀티턴) =====
    # {"role": "user" | "assistant", "content": str} 형태로 누적
    messages: NotRequired[list[dict]]

    # ===== 여행 단계 =====
    travel_phase: NotRequired[TravelPhase]        # "pre_trip" | "during_trip" | "unknown"

    # ===== 현재 시각 (Asia/Seoul) =====
    current_datetime: NotRequired[str]            # 예: "2026년 5월 19일" — worker까지 전달

    # ===== Supervisor intake 처리 중 =====
    tpo_context: NotRequired[TpoContext]
    has_tpo_conflict: NotRequired[bool]           # True면 사용자에게 선택지 제시
    needs_user_clarification: NotRequired[bool]   # True면 되묻기 후 대기
    clarification_question: NotRequired[str]      # 되묻기 질문 텍스트
    clarification_type: NotRequired[str]          # "tpo_conflict" | "routing" | "info" | "past_date"

    # 충돌/추가질문 대기 중 임시 보관 (되묻기 해소 후 이어서 처리하기 위해)
    _pending_keywords: NotRequired[list[dict]]    # 추출된 키워드 임시 저장 (충돌 시)
    _carried_keywords: NotRequired[list[dict]]    # 범위 밖 안내 후 다음 발화로 이어받을 키워드
    _surfy_user_context: NotRequired[dict]         # Surfy API payload user_context 임시 전달용
    _surfy_history: NotRequired[list[dict]]        # Surfy API payload history 임시 전달용

    # ===== 멀티턴 누적 키워드 컨텍스트 =====
    # raw 발화 전체 대신 핵심 키워드만 카테고리별로 누적해서 보관한다.
    # Supervisor가 매 턴 업데이트하고 다음 턴 키워드 추출 시 LLM 컨텍스트로 주입한다.
    accumulated_keywords: NotRequired[dict]
    # 구조 예시:
    # {
    #   "location":   ["홍대"],        ← 가장 최근 지역 (교체)
    #   "mood":       ["조용한"],      ← 누적된 선호 분위기 (누적)
    #   "place_type": ["카페"],        ← 가장 최근 장소 유형 (교체)
    #   "food_type":  ["한식"],        ← 가장 최근 음식 유형 (교체)
    #   "suppressed": ["체인"],        ← 거부 키워드 (누적, 계속 기억)
    # }

    # ===== Supervisor intake 출력 =====
    target_agents: NotRequired[list[str]]                      # 라우팅할 에이전트 목록
    taste_context: NotRequired[TasteContext]                   # 통합 취향 객체
    agent_taste_contexts: NotRequired[dict]                    # agent별로 필터링된 취향 객체
    keywords_with_reasons: NotRequired[list[KeywordWithReason]]  # 키워드 + 근거

    # ===== Worker Agent 결과 (병합용) =====
    tourist_result: NotRequired[dict]
    foodie_result: NotRequired[dict]
    restaurant_result: NotRequired[dict]
    event_result: NotRequired[dict]

    # ===== 최종 응답 =====
    final_response: NotRequired[dict]
