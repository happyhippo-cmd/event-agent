"""
K-Dive Supervisor Agent — 검증 스크립트 (대화형 + 자동 케이스)

실행 방법:
  cd surfy-backend
  python supervisor_validation.py            # 대화형 REPL (기본 잔잔한 음악 프로필)
  python supervisor_validation.py --tpo      # 대화형 REPL (힙합/EDM 프로필) → TPO 충돌 검증
  python supervisor_validation.py --cases    # 자동 케이스 검증 (PASS/FAIL, supervisor 단까지)

종료(대화형): Ctrl+C 또는 'exit' 입력
"""

import argparse
import sys
import os
import warnings
from typing import Callable

# Pydantic 직렬화 경고 숨기기 (LangChain 버전 호환 이슈, 동작에는 영향 없음)
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

# surfy-backend/ 를 기준으로 apps 패키지를 찾을 수 있게 경로 추가
sys.path.insert(0, os.path.dirname(__file__))

# .env 파일에서 API 키 불러오기
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from apps.agents.state import AGENT_FOODIE, KDiveState, OnboardingData, PreviousTurn
from apps.agents.supervisor import supervisor_intake, continue_after_clarification
# 주의: restaurant worker(run_foodie_agent_for_state)는 chromadb 등 무거운 의존성을 끌어온다.
# 자동 케이스(--cases)는 supervisor 단까지만 검증하므로 worker 를 import 하지 않는다.
# 대화형 모드(run_interactive)에서만 지연 import 한다.

# ============================================================
# 더미 데이터 — 테스트용 가상 사용자 프로필
# ============================================================

# 온보딩: 사용자가 처음 앱에서 선택한 취향 데이터
DUMMY_ONBOARDING: OnboardingData = {
    "music": ["애틋한", "시네마", "청량한", "벅찬", "희망찬", "찬란한"],
    "tourist_spots": ["남산서울타워", "세운상가 옥상", "여의도 한강공원"],
    "foodie_spots": ["남산 돈가스", "화덕피자집", "초밥집"],
    "preferred_mood": ["애틋한", "청량한", "희망찬"],
    "companion_type": "혼자",
    "active_time": "저녁",
}

# 사용자 히스토리: 직전 대화 턴 기록 (지난번 추천 내역)
DUMMY_PREVIOUS_TURN: PreviousTurn = {
    "user_reaction": "positive",                           # 지난 추천에 만족했음
    "last_recommendation": ["앤트러사이트 홍대", "카페 노티드"],  # 지난번에 추천했던 곳
    "last_keywords": ["감성 카페", "조용한"],                # 지난번에 사용된 키워드
}

# 자동 케이스 6 (TPO 충돌) 전용 — 활기찬 음악 취향 프로필
ONBOARDING_ENERGETIC: OnboardingData = {
    "music": ["힙합", "EDM", "신나는"],
    "tourist_spots": ["홍대 놀이터"],
    "foodie_spots": ["홍대 술집"],
    "preferred_mood": ["활기찬", "신나는"],
    "companion_type": "친구",
    "active_time": "밤",
}

# ============================================================
# 대화형 모드 — 결과 출력 헬퍼
# ============================================================

def print_separator(char="─", width=60):
    print(char * width)

def print_result(state: KDiveState):
    """Supervisor 처리 결과를 읽기 쉽게 출력한다."""
    print()
    print_separator("═")
    print("  🤖  Supervisor 처리 결과")
    print_separator("═")

    # 사용자에게 되물어야 하는 경우
    if state.get("needs_user_clarification"):
        print()
        if state.get("has_tpo_conflict"):
            print("  ⚠️  취향 충돌 감지! 사용자에게 선택지 제시")
        elif state.get("clarification_type") == "out_of_scope":
            print("  🌏  서비스 범위 밖 요청 — 수도권으로 유도")
        else:
            print("  ❓  추가 정보 필요")
        print()
        print("  📢  되물을 질문:")
        question = state.get("clarification_question", "")
        for line in question.splitlines():
            print(f"      {line}")
        print()
        print_separator()
        return

    # 정상 처리 결과

    # 1. 라우팅 결과
    target_agents = state.get("target_agents", [])
    agent_labels = {
        "tourist": "🗺️  관광지 Agent",
        "foodie":  "🍽️  맛집 Agent",
        "event":   "🎪  이벤트 Agent",
    }
    print()
    print("  ▶  라우팅 결정 (어느 Agent에게 넘길지)")
    for agent in target_agents:
        print(f"      → {agent_labels.get(agent, agent)}")

    # 1-1. 라우팅 근거 (키워드별 분류)
    taste = state.get("taste_context", {})
    routing_detail = taste.get("keyword_routing_detail", [])
    if routing_detail:
        hint_label = {
            "tourist": "관광지",
            "foodie":  "맛집",
            "event":   "이벤트",
            "any":     "전체",
        }
        print()
        print("  ▶  라우팅 근거 (키워드별 분류)")
        print(f"      {'키워드':<18} {'카테고리':<14} {'담당'}")
        print(f"      {'─'*18} {'─'*14} {'─'*8}")
        for detail in routing_detail:
            kw   = detail['keyword'][:16]
            cat  = detail['category']
            hint = hint_label.get(detail['agent_hint'], detail['agent_hint'])
            print(f"      {kw:<18} {cat:<14} {hint}")

    # 2. 키워드 + 근거
    print()
    print("  ▶  추출된 키워드 & 추천 근거")
    kwr_list = state.get("keywords_with_reasons", [])
    if kwr_list:
        for item in kwr_list:
            print(f"      • {item['keyword']}")
            print(f"        근거: {item['reason']}")
    else:
        print("      (키워드 없음)")

    # 3. 취향 객체 요약 (주요 항목만)
    print()
    print("  ▶  취향 객체 요약 (Agent에게 전달될 데이터)")
    print(f"      현재 키워드   : {taste.get('current_keywords', [])}")
    print(f"      무드 키워드   : {taste.get('mood_keywords', [])}")
    print(f"      장소 타입     : {taste.get('place_type_keywords', [])}")
    print(f"      위치          : {taste.get('location_keywords', [])}")
    print(f"      강화 키워드   : {taste.get('boosted_keywords', [])}")
    print(f"      억제 키워드   : {taste.get('suppressed_keywords', [])}")
    print(f"      anchor 허용   : {taste.get('allow_onboarding_anchors')}")

    agent_contexts = state.get("agent_taste_contexts", {})
    if agent_contexts:
        print()
        print("  ▶  Agent별 전달 키워드")
        for agent, ctx in agent_contexts.items():
            print(f"      [{agent}]")
            print(f"        현재 키워드 : {ctx.get('current_keywords', [])}")
            print(f"        위치       : {ctx.get('location_keywords', [])}")
            print(f"        장소 타입  : {ctx.get('place_type_keywords', [])}")
            print(f"        음식 타입  : {ctx.get('food_type_keywords', [])}")
            print(f"        무드       : {ctx.get('mood_keywords', [])}")

    # 4. 이전 대화 context (신규)
    conv = taste.get("conversation_context", {})
    print()
    print("  ▶  이전 대화 context (Worker에게 전달되는 내용)")
    print(f"      최근 대화     : {conv.get('recent_messages', [])}")
    print(f"      직전 추천     : {conv.get('last_recommendation', [])}")
    print(f"      직전 키워드   : {conv.get('last_keywords', [])}")
    print(f"      직전 반응     : {conv.get('user_reaction', 'none')}")
    print(f"      누적 요약     : {conv.get('accumulated_keywords', {})}")

    # 5. TPO 선택 시 그룹 분리 확인 (A/C 선택 시 무드 두 그룹으로 나뉨)
    tpo_choice = taste.get("tpo_choice")
    if tpo_choice in ("A", "C"):
        print()
        print(f"  ▶  TPO 충돌 {tpo_choice} 선택 — 무드 그룹 분리")
        print(f"      [🎵 음악 취향 기준] : {taste.get('onboarding_mood_keywords', [])}")
        print(f"      [📍 현재 발화 기준] : {taste.get('current_mood_keywords', [])}")
        if agent_contexts:
            print()
            print("  ▶  Agent별 TPO 그룹 전달")
            for agent, ctx in agent_contexts.items():
                print(f"      [{agent}]")
                print(f"        🎵 음악 취향 무드 : {ctx.get('onboarding_mood_keywords', [])}")
                print(f"        📍 현재 발화 무드 : {ctx.get('current_mood_keywords', [])}")
                print(f"        전체 무드          : {ctx.get('mood_keywords', [])}")

    # 5. 여행 단계 (신규)
    travel_phase = state.get("travel_phase", "unknown")
    phase_label = {
        "pre_trip":    "🗓️  여행 전 (계획 중)",
        "during_trip": "📍  여행 중 (현재 이동/탐색)",
        "unknown":     "❓  판단 불가",
    }
    print()
    print("  ▶  여행 단계 감지 (신규)")
    print(f"      {phase_label.get(travel_phase, travel_phase)}")

    # 6. 대화 히스토리 (신규)
    messages = state.get("messages", [])
    print()
    print(f"  ▶  대화 히스토리 누적 (신규) — 총 {len(messages)}턴")
    for msg in messages:
        role = "나" if msg["role"] == "user" else "AI"
        print(f"      [{role}] {msg['content'][:120]}")

    # 4. Foodie worker 결과
    if "tourist" in target_agents:
        tourist = state.get("tourist_result")
        print()
        print("  ▶  Tourist Agent 추천 결과")
        if not tourist:
            print("      (Tourist Agent가 아직 실행되지 않음)")
        elif tourist.get("status") == "error" or tourist.get("error"):
            print(f"      메시지: {tourist.get('message') or tourist.get('error')}")
        else:
            print(f"      기준 위치: {tourist.get('current_location')}")
            for idx, place in enumerate(tourist.get("recommended_places", [])[:3], start=1):
                print(f"      {idx}. {place.get('place_name') or place.get('name')}")

    if AGENT_FOODIE in target_agents:
        foodie = state.get("foodie_result")
        print()
        print("  ▶  Foodie Agent 추천 결과")
        if not foodie:
            print("      (Foodie Agent가 아직 실행되지 않음)")
        elif foodie.get("status") != "ok":
            print(f"      상태: {foodie.get('status')}")
            print(f"      메시지: {foodie.get('message')}")
        else:
            print(f"      검색 쿼리: {foodie.get('query')}")
            for idx, place in enumerate(foodie.get("candidates", []), start=1):
                print(
                    f"      {idx}. {place['name']} "
                    f"({place['gu']} / {place['category']})"
                )
                print(f"         주소: {place['address']}")
                print(f"         근거: {place['ranking_basis']}")

    print()
    print_separator()

# ============================================================
# 대화형 모드 — 메인 루프
# ============================================================

def run_interactive(use_tpo_profile: bool = False):
    """
    대화형 테스트 모드.

    Args:
        use_tpo_profile: True 면 ONBOARDING_ENERGETIC (힙합/EDM) 프로필 사용 → TPO 충돌 검증용
                         False(기본)면 DUMMY_ONBOARDING (잔잔한 음악) 프로필 사용
    """
    # 대화형 모드에서만 worker 를 지연 import (chromadb 등 무거운 의존성)
    from apps.agents.workers.restaurant import (
        run_restaurant_agent_for_state as run_foodie_agent_for_state,
    )
    from apps.agents.workers.tour.agent import run_tour_agent_for_state

    onboarding = ONBOARDING_ENERGETIC if use_tpo_profile else DUMMY_ONBOARDING
    profile_label = "⚡ 활기찬 음악 (TPO 충돌 테스트용)" if use_tpo_profile else "🎵 잔잔한 음악 (기본)"

    print()
    print_separator("═")
    print("  🌊  K-Dive Supervisor Agent — 대화형 테스트 모드")
    print_separator("═")
    print()
    print("  📋  더미 사용자 프로필 로드됨")
    print(f"      프로필        : {profile_label}")
    print(f"      음악 취향     : {onboarding['music']}")
    print(f"      선호 관광지   : {onboarding['tourist_spots']}")
    print(f"      선호 맛집     : {onboarding['foodie_spots']}")
    print(f"      직전 반응     : {DUMMY_PREVIOUS_TURN['user_reaction']}")
    print(f"      직전 추천     : {DUMMY_PREVIOUS_TURN['last_recommendation']}")
    print()
    print("  💬  사용자 메시지를 입력하세요. 종료하려면 'exit' 입력.")
    print()

    # 대화 히스토리 (멀티턴 검증용 — 세션 내 누적)
    session_messages: list[dict] = []
    session_accumulated_keywords: dict = {}

    # 되묻기 대기 중인 state 보관 (A/B/C 응답 처리용)
    pending_clarification_state: KDiveState | None = None

    while True:
        try:
            # 되묻기 중이면 프롬프트에 힌트 표시
            if pending_clarification_state is not None:
                c_type = pending_clarification_state.get("clarification_type", "tpo_conflict")
                if c_type == "routing":
                    prompt = "  나 (1/2/3) > "
                elif c_type == "out_of_scope":
                    prompt = "  나 > "
                else:
                    prompt = "  나 (A/B/C) > "
            else:
                prompt = "  나 > "
            user_input = input(prompt).strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\n  👋  테스트 종료.")
            break

        if not user_input:
            continue
        if user_input.lower() == "exit":
            print("\n  👋  테스트 종료.")
            break

        print()
        print("  ⏳  Supervisor 처리 중...")

        try:
            # ── 되묻기 응답 처리 (A/B/C 또는 자유 답변) ──
            if pending_clarification_state is not None:
                result_state = continue_after_clarification(
                    pending_state=pending_clarification_state,
                    user_choice=user_input,
                )
                pending_clarification_state = None
                session_messages = list(result_state.get("messages") or session_messages)
                session_accumulated_keywords = dict(
                    result_state.get("accumulated_keywords") or session_accumulated_keywords
                )
                if not result_state.get("needs_user_clarification"):
                    result_state = run_tour_agent_for_state(result_state)
                    result_state = run_foodie_agent_for_state(result_state)

            # ── 새 발화 처리 ──
            else:
                state: KDiveState = {
                    "user_utterance": user_input,
                    "onboarding_data": onboarding,
                    "previous_turn": DUMMY_PREVIOUS_TURN,
                    "messages": list(session_messages),  # supervisor가 내부에서 append함
                    "accumulated_keywords": dict(session_accumulated_keywords),
                }
                result_state = supervisor_intake(state)

                # supervisor가 누적한 messages를 세션에 동기화
                session_messages = list(result_state.get("messages") or [])
                session_accumulated_keywords = dict(result_state.get("accumulated_keywords") or {})

                if not result_state.get("needs_user_clarification"):
                    result_state = run_tour_agent_for_state(result_state)
                    result_state = run_foodie_agent_for_state(result_state)

            # 되묻기가 필요한 경우 → 다음 입력을 위해 보관
            if result_state.get("needs_user_clarification"):
                pending_clarification_state = result_state

            print_result(result_state)

        except Exception as e:
            print()
            print(f"  ❌  오류 발생: {e}")
            print("      .env 파일에 OPENAI_API_KEY가 올바르게 설정됐는지 확인해줘.")
            print()
            pending_clarification_state = None  # 오류 시 대기 상태 초기화

# ============================================================
# 자동 케이스 모드 — 헬퍼
# ============================================================

def _initial_state(utterance: str, onboarding: OnboardingData) -> KDiveState:
    return {"user_utterance": utterance, "onboarding_data": onboarding}


def _short(value, limit: int = 80) -> str:
    s = repr(value)
    return s if len(s) <= limit else s[:limit] + "..."


def _show(label: str, state: KDiveState) -> None:
    tc = state.get("taste_context") or {}
    print(f"  [{label}]")
    print(f"    needs_clarification  = {state.get('needs_user_clarification')}")
    print(f"    clarification_type   = {state.get('clarification_type')}")
    print(f"    has_tpo_conflict     = {state.get('has_tpo_conflict')}")
    print(f"    target_agents        = {state.get('target_agents')}")
    print(f"    location_keywords    = {tc.get('location_keywords')}")
    print(f"    mood_keywords        = {tc.get('mood_keywords')}")
    print(f"    place_type_keywords  = {tc.get('place_type_keywords')}")
    print(f"    food_type_keywords   = {tc.get('food_type_keywords')}")
    print(f"    suppressed_keywords  = {tc.get('suppressed_keywords')}")
    print(f"    boosted_keywords     = {tc.get('boosted_keywords')}")
    print(f"    tpo_choice           = {tc.get('tpo_choice')}")
    print(f"    onboarding_mood_kws  = {tc.get('onboarding_mood_keywords')}")
    print(f"    current_mood_kws     = {tc.get('current_mood_keywords')}")
    print(f"    allow_onbd_anchors   = {tc.get('allow_onboarding_anchors')}")
    routing_detail = tc.get("keyword_routing_detail")
    if routing_detail:
        print(f"    keyword_routing_detail:")
        for item in routing_detail:
            print(f"      - {item}")
    if state.get("clarification_question"):
        print(f"    question[:80]        = {_short(state['clarification_question'], 80)}")
    if state.get("_carried_keywords") is not None:
        carried = [c.get("keyword") for c in state["_carried_keywords"]]
        print(f"    _carried_keywords    = {carried}")
    if state.get("accumulated_keywords") is not None:
        print(f"    accumulated_keywords = {state.get('accumulated_keywords')}")


# ============================================================
# 자동 케이스 정의
# ============================================================

def case_1_explicit_location_vs_onboarding() -> tuple[str, list[tuple[str, bool]]]:
    title = "1) 명시 지역 vs 온보딩 좌표 (성수동 + 온보딩 남산)"
    state = supervisor_intake(_initial_state("성수동에서 디저트 카페 추천해줘", DUMMY_ONBOARDING))
    _show("intake", state)

    tc = state.get("taste_context") or {}
    locs = tc.get("location_keywords") or []
    checks = [
        ("foodie 라우팅", "foodie" in (state.get("target_agents") or [])),
        ("location_keywords에 '성수' 포함", any("성수" in k for k in locs)),
        ("allow_onboarding_anchors == False", tc.get("allow_onboarding_anchors") is False),
        ("clarification 없음", not state.get("needs_user_clarification")),
    ]
    return title, checks


def case_2_subway_station_normalization() -> tuple[str, list[tuple[str, bool]]]:
    title = "2) 지하철역 정규화 (강남역 근처 조용한 카페)"
    state = supervisor_intake(_initial_state("강남역 근처 조용한 카페 추천해줘", DUMMY_ONBOARDING))
    _show("intake", state)

    tc = state.get("taste_context") or {}
    locs = tc.get("location_keywords") or []
    moods = tc.get("mood_keywords") or []
    checks = [
        ("foodie 라우팅", "foodie" in (state.get("target_agents") or [])),
        ("location_keywords에 정규화된 '강남' 포함",
         any(k == "강남" or ("강남" in k and "역" not in k) for k in locs)),
        ("mood_keywords에 '조용' 의도 포함", any("조용" in m for m in moods)),
        ("allow_onboarding_anchors == False", tc.get("allow_onboarding_anchors") is False),
    ]
    return title, checks


def case_3_compound_intent() -> tuple[str, list[tuple[str, bool]]]:
    title = "3) 복합 의도 (북촌 구경 + 근처 맛집)"
    state = supervisor_intake(_initial_state("북촌 구경하고 근처에서 밥도 먹고 싶어", DUMMY_ONBOARDING))
    _show("intake", state)

    targets = state.get("target_agents") or []
    agent_contexts = state.get("agent_taste_contexts") or {}
    tourist_ctx = agent_contexts.get("tourist") or {}
    foodie_ctx = agent_contexts.get("foodie") or {}
    checks = [
        ("tourist 라우팅", "tourist" in targets),
        ("foodie 라우팅", "foodie" in targets),
        ("clarification 없음", not state.get("needs_user_clarification")),
        ("tourist context에 구경 포함", "구경" in (tourist_ctx.get("current_keywords") or [])),
        ("foodie context에 음식 의도 포함", bool(foodie_ctx.get("current_keywords"))),
        ("foodie context에 관광 activity 미포함", "구경" not in (foodie_ctx.get("current_keywords") or [])),
    ]
    return title, checks


def case_4_negation() -> tuple[str, list[tuple[str, bool]]]:
    title = "4) 부정·배제 (체인 말고 로컬 카페)"
    state = supervisor_intake(_initial_state("체인 말고 로컬 카페로 추천해줘", DUMMY_ONBOARDING))
    _show("intake", state)

    tc = state.get("taste_context") or {}
    suppressed = tc.get("suppressed_keywords") or []
    checks = [
        ("foodie 라우팅", "foodie" in (state.get("target_agents") or [])),
        ("suppressed_keywords 비어있지 않음", len(suppressed) > 0),
    ]
    return title, checks


def case_5_routing_ambiguous() -> tuple[str, list[tuple[str, bool]]]:
    title = "5) 라우팅 애매 → 사용자 선택('2') → 재진입"
    state = supervisor_intake(_initial_state("주말에 뭐 할까", DUMMY_ONBOARDING))
    _show("intake (1차)", state)

    first_ok = (
        state.get("needs_user_clarification") is True
        and state.get("clarification_type") == "routing"
    )

    if first_ok:
        state2 = continue_after_clarification(state, "2")
        _show("after '2' (재진입)", state2)
        targets = state2.get("target_agents") or []
        checks = [
            ("1차에서 routing 질문", True),
            ("재진입 후 needs_clarification False", not state2.get("needs_user_clarification")),
            ("재진입 후 foodie 라우팅", "foodie" in targets),
            ("재진입 후 tourist·event 미포함", "tourist" not in targets and "event" not in targets),
        ]
    else:
        checks = [
            ("1차에서 routing 질문",
             state.get("needs_user_clarification") is True
             and state.get("clarification_type") == "routing"),
        ]
    return title, checks


def case_6_tpo_conflict_c() -> tuple[str, list[tuple[str, bool]]]:
    title = "6) TPO 충돌 (활기찬 음악 + 조용한 카페) → 'C' 선택"
    state = supervisor_intake(_initial_state("조용한 카페에서 책 읽고 싶어", ONBOARDING_ENERGETIC))
    _show("intake (1차)", state)

    conflict = state.get("has_tpo_conflict") is True
    if conflict:
        state2 = continue_after_clarification(state, "C")
        _show("after 'C' (재진입)", state2)
        tc2 = state2.get("taste_context") or {}
        checks = [
            ("1차에서 TPO 충돌 감지", True),
            ("재진입 후 tpo_choice == 'C'", tc2.get("tpo_choice") == "C"),
            ("onboarding_mood_keywords 채워짐", bool(tc2.get("onboarding_mood_keywords"))),
            ("current_mood_keywords 채워짐 (조용 관련)",
             any("조용" in m for m in tc2.get("current_mood_keywords") or [])),
        ]
    else:
        checks = [
            ("1차에서 TPO 충돌 감지", False),
            ("(skipped) 충돌 미감지로 후속 검증 생략", True),
        ]
    return title, checks


def case_7_past_date_two_branches() -> tuple[str, list[tuple[str, bool]]]:
    title = "7) 과거 날짜 (5월 5일) → 두 갈래 응답"
    state = supervisor_intake(_initial_state("5월 5일에 갈 건데 카페 추천해줘", DUMMY_ONBOARDING))
    _show("intake (1차)", state)

    past = (
        state.get("needs_user_clarification") is True
        and state.get("clarification_type") == "past_date"
    )

    branch_a_ok = branch_b_ok = False
    if past:
        state_a = continue_after_clarification(state, "응 현재 기준으로")
        _show("branch A: '현재 기준으로'", state_a)
        branch_a_ok = (
            not state_a.get("needs_user_clarification")
            or state_a.get("clarification_type") != "past_date"
        )

        state_b = continue_after_clarification(state, "그럼 5월 25일에 갈게")
        _show("branch B: '5월 25일에'", state_b)
        branch_b_ok = state_b.get("clarification_type") != "past_date"

    checks = [
        ("1차에서 past_date 감지", past),
        ("branch A (현재 기준)에서 past_date 해소", branch_a_ok),
        ("branch B (새 날짜)에서 past_date 해소", branch_b_ok),
    ]
    return title, checks


def case_8_out_of_scope_carryover() -> tuple[str, list[tuple[str, bool]]]:
    title = "8) out_of_scope (제주도) → '홍대로' carry-over"
    state = supervisor_intake(_initial_state("제주도에서 책 읽기 좋은 카페 추천해줘", DUMMY_ONBOARDING))
    _show("intake (1차)", state)

    oos = (
        state.get("needs_user_clarification") is True
        and state.get("clarification_type") == "out_of_scope"
    )
    carried_first = state.get("_carried_keywords") or []

    if oos:
        state2 = continue_after_clarification(state, "그럼 홍대로 추천해줘")
        _show("after '홍대로' (재진입)", state2)
        tc2 = state2.get("taste_context") or {}
        locs2 = tc2.get("location_keywords") or []
        food_types = tc2.get("food_type_keywords") or []
        place_types = tc2.get("place_type_keywords") or []
        cafe_carried = any("카페" in k for k in (food_types + place_types))
        checks = [
            ("1차에서 out_of_scope 감지", True),
            ("1차 _carried_keywords 비어있지 않음", len(carried_first) > 0),
            ("재진입 후 foodie 라우팅", "foodie" in (state2.get("target_agents") or [])),
            ("재진입 후 location에 '홍대' 포함", any("홍대" in k for k in locs2)),
            ("재진입 후 '카페' 키워드 carry 됨", cafe_carried),
            ("재진입 후 allow_onboarding_anchors == False",
             tc2.get("allow_onboarding_anchors") is False),
        ]
    else:
        checks = [("1차에서 out_of_scope 감지", False)]
    return title, checks


def case_9_structured_multiturn_memory() -> tuple[str, list[tuple[str, bool]]]:
    title = "9) 구조화 멀티턴 메모리 (오래된 날짜 제외 + 북촌 보존)"
    messages: list[dict] = []
    accumulated: dict = {}

    for utterance in (
        "5월 5일에 한국여행 갈거야. 광화문 구경 갈건데, 주변에 더 볼만한 관광지 있어?",
        "혜화역 조용한 카페 추천해줘",
    ):
        state = supervisor_intake(
            {
                "user_utterance": utterance,
                "onboarding_data": DUMMY_ONBOARDING,
                "messages": list(messages),
                "accumulated_keywords": dict(accumulated),
            }
        )
        messages = list(state.get("messages") or messages)
        accumulated = dict(state.get("accumulated_keywords") or accumulated)

    state = supervisor_intake(
        {
            "user_utterance": "북촌 구경하고 근처 맛집도 알려줘",
            "onboarding_data": DUMMY_ONBOARDING,
            "messages": list(messages),
            "accumulated_keywords": dict(accumulated),
        }
    )
    _show("intake", state)

    tc = state.get("taste_context") or {}
    current = tc.get("current_keywords") or []
    locs = tc.get("location_keywords") or []
    targets = state.get("target_agents") or []
    checks = [
        ("location_keywords에 '북촌' 포함", any(k == "북촌" for k in locs)),
        ("잘린 location '촌' 미포함", "촌" not in locs and "촌" not in current),
        ("오래된 날짜 '5월 5일' 미포함", not any("5월 5일" in k for k in current)),
        ("tourist 라우팅", "tourist" in targets),
        ("foodie 라우팅", "foodie" in targets),
    ]
    return title, checks


def case_10_tpo_conflict_calm_music_noisy_place() -> tuple[str, list[tuple[str, bool]]]:
    title = "10) TPO 충돌 (차분한 음악 + 클럽/라운지 바)"
    state = supervisor_intake(
        _initial_state("시크러운 클럽이나 라운지 바 가고싶어. 추천해줄 곳 있어", DUMMY_ONBOARDING)
    )
    _show("intake (1차)", state)

    conflict = state.get("has_tpo_conflict") is True
    if conflict:
        state2 = continue_after_clarification(state, "C")
        _show("after 'C' (재진입)", state2)
        tc2 = state2.get("taste_context") or {}
        checks = [
            ("1차에서 TPO 충돌 감지", True),
            ("재진입 후 tpo_choice == 'C'", tc2.get("tpo_choice") == "C"),
            ("현재 장소 타입에 클럽/라운지 포함",
             any("클럽" in k or "라운지" in k for k in tc2.get("place_type_keywords") or [])),
            ("온보딩 무드 그룹 채워짐", bool(tc2.get("onboarding_mood_keywords"))),
        ]
    else:
        checks = [("1차에서 TPO 충돌 감지", False)]
    return title, checks


def case_11_agent_context_split_and_no_leakage() -> tuple[str, list[tuple[str, bool]]]:
    title = "11) Agent별 키워드 분리 + 명시 follow-up 아닐 때 이전 의도 미누수"
    messages: list[dict] = []
    accumulated: dict = {}
    state1 = supervisor_intake(
        {
            "user_utterance": "성수에서 구경하고 초밥도 먹고싶어.",
            "onboarding_data": DUMMY_ONBOARDING,
            "messages": messages,
            "accumulated_keywords": accumulated,
        }
    )
    _show("turn1", state1)
    messages = list(state1.get("messages") or [])
    accumulated = dict(state1.get("accumulated_keywords") or {})

    agent_contexts = state1.get("agent_taste_contexts") or {}
    tourist_ctx = agent_contexts.get("tourist") or {}
    foodie_ctx = agent_contexts.get("foodie") or {}

    state2 = supervisor_intake(
        {
            "user_utterance": "조용한 카페에서 책 읽고 싶어",
            "onboarding_data": DUMMY_ONBOARDING,
            "messages": messages,
            "accumulated_keywords": accumulated,
        }
    )
    _show("turn2", state2)
    tc2 = state2.get("taste_context") or {}
    current2 = tc2.get("current_keywords") or []

    checks = [
        ("turn1 tourist context = 성수/구경 중심",
         "구경" in (tourist_ctx.get("current_keywords") or [])
         and "초밥" not in (tourist_ctx.get("current_keywords") or [])),
        ("turn1 foodie context = 성수/초밥 중심",
         "초밥" in (foodie_ctx.get("current_keywords") or [])
         and "구경" not in (foodie_ctx.get("current_keywords") or [])),
        ("turn2 current_keywords에 이전 성수 미포함", "성수" not in current2),
        ("turn2 current_keywords에 이전 초밥 미포함", "초밥" not in current2),
        ("turn2 조용한 카페 의도 유지",
         "조용한" in current2 and "카페" in current2),
    ]
    return title, checks


def case_12_tpo_choice_a_music_basis() -> tuple[str, list[tuple[str, bool]]]:
    title = "12) TPO 충돌 A 선택 → 음악 취향 기준 재구성"
    state = supervisor_intake(
        _initial_state("조용한 카페에서 책 읽고 싶어", ONBOARDING_ENERGETIC)
    )
    _show("intake (1차)", state)
    if state.get("has_tpo_conflict") is not True:
        return title, [("1차에서 TPO 충돌 감지", False)]

    state2 = continue_after_clarification(state, "A")
    _show("after 'A' (재진입)", state2)
    tc2 = state2.get("taste_context") or {}
    current = tc2.get("current_keywords") or []
    checks = [
        ("재진입 후 tpo_choice == 'A'", tc2.get("tpo_choice") == "A"),
        ("음악 취향 키워드 포함", any(k in current for k in ("힙합", "EDM", "신나는"))),
        ("현재 요청 장소 타입 카페 유지", "카페" in (tc2.get("place_type_keywords") or [])),
        ("현재 요청 무드 조용한은 current_mood에서 제외",
         "조용한" not in (tc2.get("current_mood_keywords") or [])),
        ("foodie 라우팅 유지", "foodie" in (state2.get("target_agents") or [])),
    ]
    return title, checks


# ============================================================
# 자동 케이스 모드 — 실행
# ============================================================

CASES: list[Callable[[], tuple[str, list[tuple[str, bool]]]]] = [
    case_1_explicit_location_vs_onboarding,
    case_2_subway_station_normalization,
    case_3_compound_intent,
    case_4_negation,
    case_5_routing_ambiguous,
    case_6_tpo_conflict_c,
    case_7_past_date_two_branches,
    case_8_out_of_scope_carryover,
    case_9_structured_multiturn_memory,
    case_10_tpo_conflict_calm_music_noisy_place,
    case_11_agent_context_split_and_no_leakage,
    case_12_tpo_choice_a_music_basis,
]


def run_cases() -> int:
    summary: list[tuple[str, int, int]] = []
    for case in CASES:
        print("=" * 70)
        try:
            title, checks = case()
        except Exception as exc:
            title = case.__name__
            print(f"[{title}] EXCEPTION: {exc!r}")
            summary.append((title, 0, 1))
            continue
        print(f"\n  ▶ {title}")
        passed = 0
        for name, ok in checks:
            mark = "PASS" if ok else "FAIL"
            print(f"    [{mark}] {name}")
            if ok:
                passed += 1
        summary.append((title, passed, len(checks)))
        print()

    print("=" * 70)
    print("  SUMMARY")
    print("=" * 70)
    total_pass = total = 0
    for title, p, t in summary:
        total_pass += p
        total += t
        print(f"  {p}/{t}  {title}")
    print(f"\n  Overall: {total_pass}/{total}")
    return 0 if total_pass == total else 1


# ============================================================
# 진입점 — 모드 분기
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="K-Dive Supervisor 검증 스크립트 (대화형 + 자동 케이스)"
    )
    parser.add_argument(
        "--cases", "-c",
        action="store_true",
        help="자동 케이스 검증 모드 (기본은 대화형 REPL)",
    )
    parser.add_argument(
        "--tpo",
        action="store_true",
        help="대화형 모드에서 활기찬 음악 취향 프로필(힙합/EDM) 사용 → TPO 충돌 검증용",
    )
    args = parser.parse_args()

    if args.cases:
        raise SystemExit(run_cases())
    run_interactive(use_tpo_profile=args.tpo)


if __name__ == "__main__":
    main()
