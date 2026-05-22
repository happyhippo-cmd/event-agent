"""
K-Dive Agent Graph
LangGraph StateGraph + MemorySaver 기반 멀티턴 대화 그래프

사용법:
    from apps.agents.graph import build_graph

    # workers_node: supervisor가 선택한 worker를 실행하는 함수 (필수)
    graph = build_graph(workers_node=run_workers)

    # 첫 번째 턴
    result = graph.invoke(
        {
            "user_utterance": "홍대 근처 감성 카페 추천해줘",
            "onboarding_data": onboarding,
        },
        config={"configurable": {"thread_id": "user-123"}},
    )

    # 두 번째 턴 (같은 thread_id → 이전 대화 기억)
    result = graph.invoke(
        {"user_utterance": "거기서 가까운 맛집도 알려줘"},
        config={"configurable": {"thread_id": "user-123"}},
    )

LangSmith 자동 트레이싱:
    .env 또는 환경변수에 아래 세 값을 설정하면 graph.invoke() 호출마다
    전체 실행 흐름이 LangSmith 프로젝트에 자동으로 기록된다.

        LANGCHAIN_TRACING_V2=true
        LANGCHAIN_API_KEY=lsv2_pt_...
        LANGCHAIN_PROJECT=final-kdive-surfy

    폴백 케이스(이전 추천 전면 거부)는 supervisor_intake()에서
    "fallback" 태그와 메타데이터를 LangSmith 트레이스에 자동으로 추가한다.
"""

from collections.abc import Callable

from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.memory import MemorySaver

from .state import KDiveState, AGENT_TOURIST, AGENT_FOODIE, AGENT_EVENT
from .supervisor import supervisor_intake, continue_after_clarification

# Worker 임포트 — 각 에이전트의 for_state 인터페이스 사용
from .workers.restaurant import run_restaurant_agent_for_state
from .workers.foodie import run_foodie_agent_for_state
from .workers.event import run_event_agent_for_state
from .workers.tour.agent import run_tour_agent_for_state


# ============================================================
# Worker 노드 래퍼 함수
# ============================================================


def run_tourist_node(state: KDiveState) -> KDiveState:
    """Tour worker 노드."""
    return run_tour_agent_for_state(state)


def run_foodie_node(state: KDiveState) -> KDiveState:
    """Foodie worker 노드."""
    return run_foodie_agent_for_state(state)


def run_restaurant_node(state: KDiveState) -> KDiveState:
    """Restaurant worker 노드."""
    return run_restaurant_agent_for_state(state)


def run_event_node(state: KDiveState) -> KDiveState:
    """Event worker 노드."""
    return run_event_agent_for_state(state)


def run_workers_node(state: KDiveState) -> KDiveState:
    """Supervisor가 선택한 worker만 순차 실행한다."""
    targets = state.get("target_agents") or []
    if AGENT_TOURIST in targets:
        state = run_tour_agent_for_state(state)
    if AGENT_FOODIE in targets:
        state = run_restaurant_agent_for_state(state)
    if AGENT_EVENT in targets:
        state = run_event_agent_for_state(state)
    return state

# ============================================================
# 되묻기 해소 노드 — MemorySaver가 이전 state를 복원한 뒤 진입
# ============================================================


def clarification_resolver_node(state: KDiveState) -> KDiveState:
    """
    이전 턴에서 needs_user_clarification=True 였을 때,
    사용자의 응답(user_utterance)을 continue_after_clarification()에 넘겨 처리한다.
    """
    return continue_after_clarification(
        pending_state=state,
        user_choice=state["user_utterance"],
    )


def route_at_start(state: KDiveState) -> str:
    """
    MemorySaver가 이전 state를 복원했을 때 진입 노드를 결정한다.

    - 이전 턴에 되묻기가 남아있으면 → clarification_resolver
    - 새 대화이거나 되묻기가 없으면 → supervisor
    """
    if state.get("needs_user_clarification"):
        return "clarification_resolver"
    return "supervisor"


# ============================================================
# 라우팅 함수 — supervisor 결과에 따라 다음 노드 결정
# ============================================================

def route_after_supervisor(state: KDiveState) -> str:
    """
    supervisor_intake 결과를 보고 다음 노드를 결정한다.

    - needs_user_clarification=True : 사용자에게 되물어야 하므로 "done"
    - target_agents가 있으면 선택된 모든 worker를 실행
    """
    if state.get("needs_user_clarification"):
        return "done"

    target_agents: list[str] = state.get("target_agents") or []
    return "workers" if target_agents else "done"


def _build_assistant_message(state: KDiveState) -> str:
    """
    worker 결과 또는 되묻기 질문을 assistant 메시지 텍스트로 변환한다.

    - needs_user_clarification=True  → clarification_question 반환
    - 정상 추천 케이스               → 각 worker 결과를 간단히 요약해서 반환
    """
    if state.get("needs_user_clarification"):
        return state.get("clarification_question") or ""

    lines: list[str] = []

    # 관광지 결과
    tourist = state.get("tourist_result") or {}
    places = tourist.get("recommended_places", [])
    if places:
        names = [p.get("place_name") or p.get("name", "") for p in places[:3]]
        lines.append("🗺️ 관광지 추천: " + ", ".join(n for n in names if n))
    elif tourist.get("error"):
        lines.append(f"🗺️ 관광지: {tourist['error']}")

    # 맛집 결과
    restaurant = state.get("restaurant_result") or {}
    if restaurant.get("status") == "ok":
        candidates = restaurant.get("candidates", [])
        names = [c.get("name", "") for c in candidates[:3]]
        lines.append("🍽️ 맛집 추천: " + ", ".join(n for n in names if n))
    elif restaurant.get("message"):
        lines.append(f"🍽️ 맛집: {restaurant['message']}")

    # 이벤트 결과
    event = state.get("event_result") or {}
    if event.get("status") == "ok" and event.get("message"):
        lines.append(f"🎪 이벤트: {event['message'][:200]}")
    elif event.get("message"):
        lines.append(f"🎪 이벤트: {event['message']}")

    return "\n".join(lines) if lines else ""


def done_node(state: KDiveState) -> dict:
    """
    그래프 종료 노드.
    assistant 응답(추천 결과 또는 되묻기 질문)을 messages에 추가한다.
    """
    content = _build_assistant_message(state)
    if not content:
        return {}

    messages = list(state.get("messages") or [])
    messages.append({"role": "assistant", "content": content})
    return {"messages": messages}


# ============================================================
# 그래프 빌드 함수
# ============================================================


def build_graph(after_supervisor=None, workers_node=None) -> StateGraph:
    """
    MemorySaver가 붙은 컴파일된 LangGraph를 반환한다.

    thread_id가 같으면 이전 대화 state(messages, travel_phase 등)를 이어받는다.

    Args:
        after_supervisor: supervisor/clarification_resolver 실행 후 state를 후처리하는
                          훅 함수 (optional). needs_user_clarification=False일 때만 호출된다.
                          dummy_server 등 외부에서 taste 정규화 로직을 주입할 때 사용.
        workers_node:     기본 run_workers_node 대신 사용할 커스텀 workers 노드 함수 (optional).

    Returns:
        CompiledGraph: .invoke() / .stream() 으로 사용 가능한 그래프
    """

    def _wrap_with_hook(base_fn):
        """after_supervisor 훅이 있으면 base_fn 실행 후 훅을 적용한 래퍼를 반환한다."""
        if after_supervisor is None:
            return base_fn
        def _wrapped(state: KDiveState) -> KDiveState:
            state = base_fn(state)
            if not state.get("needs_user_clarification"):
                state = after_supervisor(state)
            return state
        return _wrapped

    builder = StateGraph(KDiveState)

    # 노드 등록
    builder.add_node("supervisor", _wrap_with_hook(supervisor_intake))
    builder.add_node("clarification_resolver", _wrap_with_hook(clarification_resolver_node))
    builder.add_node("workers", workers_node if workers_node is not None else run_workers_node)
    builder.add_node("done", done_node)

    # START → 이전 턴 되묻기 여부에 따라 분기
    builder.add_conditional_edges(
        START,
        route_at_start,
        {
            "supervisor": "supervisor",
            "clarification_resolver": "clarification_resolver",
        },
    )

    # supervisor / clarification_resolver → workers 또는 done
    _after = {"workers": "workers", "done": "done"}
    builder.add_conditional_edges("supervisor", route_after_supervisor, _after)
    builder.add_conditional_edges("clarification_resolver", route_after_supervisor, _after)

    builder.add_edge("workers", "done")
    builder.add_edge("done", END)

    # MemorySaver: thread_id 별로 state를 메모리에 보관
    memory = MemorySaver()
    return builder.compile(checkpointer=memory)
