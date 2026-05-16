"""
K-Dive Agent State 정의
LangGraph 노드 간에 공유되는 전체 상태 스키마
"""

from typing import Optional, Literal
from typing_extensions import TypedDict, NotRequired

# ============================================================
# 상수 정의
# ============================================================

# Agent 라우팅 옵션
AGENT_TOURIST = "tourist"
AGENT_FOODIE = "foodie"
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

    # ===== Supervisor intake 처리 중 =====
    tpo_context: NotRequired[TpoContext]
    has_tpo_conflict: NotRequired[bool]           # True면 사용자에게 선택지 제시
    needs_user_clarification: NotRequired[bool]   # True면 되묻기 후 대기
    clarification_question: NotRequired[str]      # 되묻기 질문 텍스트
    clarification_type: NotRequired[str]          # "tpo_conflict" | "routing" | "info"

    # 충돌/추가질문 대기 중 임시 보관 (되묻기 해소 후 이어서 처리하기 위해)
    _pending_keywords: NotRequired[list[dict]]    # 추출된 키워드 임시 저장 (충돌 시)
    _carried_keywords: NotRequired[list[dict]]    # 범위 밖 안내 후 다음 발화로 이어받을 키워드

    # ===== Supervisor intake 출력 =====
    target_agents: NotRequired[list[str]]                      # 라우팅할 에이전트 목록
    taste_context: NotRequired[dict]                           # 통합 취향 객체
    keywords_with_reasons: NotRequired[list[KeywordWithReason]]  # 키워드 + 근거

    # ===== Worker Agent 결과 (병합용) =====
    tourist_result: NotRequired[dict]
    foodie_result: NotRequired[dict]
    event_result: NotRequired[dict]

    # ===== 최종 응답 =====
    final_response: NotRequired[dict]
