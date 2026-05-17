"""
K-Dive Supervisor Agent — 대화형 테스트 스크립트

실행 방법:
  cd surfy-backend
  python validation.py

종료: Ctrl+C 또는 'exit' 입력
"""

import sys
import os
import warnings

# Pydantic 직렬화 경고 숨기기 (LangChain 버전 호환 이슈, 동작에는 영향 없음)
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

# surfy-backend/ 를 기준으로 apps 패키지를 찾을 수 있게 경로 추가
sys.path.insert(0, os.path.dirname(__file__))

# .env 파일에서 API 키 불러오기
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from apps.agents.state import AGENT_FOODIE, KDiveState, OnboardingData, PreviousTurn
from apps.agents.supervisor import supervisor_intake, continue_after_clarification
from apps.agents.workers.foodie import run_foodie_agent_for_state

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

# ============================================================
# 결과 출력 헬퍼
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

    # 4. Foodie worker 결과
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
# 메인 실행 루프
# ============================================================

def main():
    print()
    print_separator("═")
    print("  🌊  K-Dive Supervisor Agent — 테스트 모드")
    print_separator("═")
    print()
    print("  📋  더미 사용자 프로필 로드됨")
    print(f"      음악 취향     : {DUMMY_ONBOARDING['music']}")
    print(f"      선호 관광지   : {DUMMY_ONBOARDING['tourist_spots']}")
    print(f"      선호 맛집     : {DUMMY_ONBOARDING['foodie_spots']}")
    print(f"      직전 반응     : {DUMMY_PREVIOUS_TURN['user_reaction']}")
    print(f"      직전 추천     : {DUMMY_PREVIOUS_TURN['last_recommendation']}")
    print()
    print("  💬  사용자 메시지를 입력하세요. 종료하려면 'exit' 입력.")
    print()

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

            # ── 새 발화 처리 ──
            else:
                state: KDiveState = {
                    "user_utterance": user_input,
                    "onboarding_data": DUMMY_ONBOARDING,
                    "previous_turn": DUMMY_PREVIOUS_TURN,
                }
                result_state = supervisor_intake(state)

            # 되묻기가 필요한 경우 → 다음 입력을 위해 보관
            if result_state.get("needs_user_clarification"):
                pending_clarification_state = result_state
            else:
                result_state = run_foodie_agent_for_state(result_state)

            print_result(result_state)

        except Exception as e:
            print()
            print(f"  ❌  오류 발생: {e}")
            print("      .env 파일에 OPENAI_API_KEY가 올바르게 설정됐는지 확인해줘.")
            print()
            pending_clarification_state = None  # 오류 시 대기 상태 초기화

if __name__ == "__main__":
    main()
