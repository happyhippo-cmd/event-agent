"""
K-Dive Agent Graph
LangGraph StateGraph + MemorySaver 기반 멀티턴 대화 그래프

사용법:
    from apps.agents.graph import build_graph

    graph = build_graph()

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
"""

from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.memory import MemorySaver

from .state import KDiveState, AGENT_TOURIST, AGENT_FOODIE, AGENT_EVENT
from .supervisor import supervisor_intake

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
    state["foodie_result"] = run_foodie_agent_for_state(state)
    return state


def run_restaurant_node(state: KDiveState) -> KDiveState:
    """Restaurant worker 노드."""
    state["restaurant_result"] = run_restaurant_agent_for_state(state)
    return state


def run_event_node(state: KDiveState) -> KDiveState:
    """Event worker 노드."""
    state["event_result"] = run_event_agent_for_state(state)
    return state


def run_workers_node(state: KDiveState) -> KDiveState:
    """Supervisor가 선택한 모든 worker를 순차 실행한다."""
    state = run_tour_agent_for_state(state)
    state = run_restaurant_agent_for_state(state)
    state = run_event_agent_for_state(state)
    return state


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


def done_node(state: KDiveState) -> dict:
    """그래프 종료 노드 — 상태 변경 없이 그래프를 끝낸다."""
    return {}


# ============================================================
# 그래프 빌드 함수
# ============================================================


def build_graph() -> StateGraph:
    """
    MemorySaver가 붙은 컴파일된 LangGraph를 반환한다.

    thread_id가 같으면 이전 대화 state(messages, travel_phase 등)를 이어받는다.

    Returns:
        CompiledGraph: .invoke() / .stream() 으로 사용 가능한 그래프
    """
    builder = StateGraph(KDiveState)

    # 노드 등록
    builder.add_node("supervisor", supervisor_intake)
    builder.add_node("tourist", run_tourist_node)
    builder.add_node("foodie", run_foodie_node)
    builder.add_node("event", run_event_node)
    builder.add_node("workers", run_workers_node)
    builder.add_node("done", done_node)

    # 시작점
    builder.add_edge(START, "supervisor")

    # supervisor 이후 조건 분기
    builder.add_conditional_edges(
        "supervisor",
        route_after_supervisor,
        {
            "workers": "workers",
            "done": "done",
        },
    )

    # 각 worker → done → END
    builder.add_edge("workers", "done")
    builder.add_edge("tourist", "done")
    builder.add_edge("foodie", "done")
    builder.add_edge("event", "done")
    builder.add_edge("done", END)

    # MemorySaver: thread_id 별로 state를 메모리에 보관
    memory = MemorySaver()
    return builder.compile(checkpointer=memory)
