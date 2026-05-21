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
"""

from collections.abc import Callable

from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.memory import MemorySaver

from .state import KDiveState
from .supervisor import supervisor_intake


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


def build_graph(
    workers_node: Callable[[KDiveState], KDiveState],
    after_supervisor: Callable[[KDiveState], KDiveState] | None = None,
) -> StateGraph:
    """
    MemorySaver가 붙은 컴파일된 LangGraph를 반환한다.

    thread_id가 같으면 이전 대화 state(messages, travel_phase 등)를 이어받는다.

    Args:
        workers_node: supervisor가 선택한 worker를 실행하는 함수 (필수)
        after_supervisor: supervisor 직후 state를 정규화하는 함수 (선택)

    Returns:
        CompiledGraph: .invoke() / .stream() 으로 사용 가능한 그래프
    """
    builder = StateGraph(KDiveState)

    # 노드 등록
    builder.add_node("supervisor", supervisor_intake)
    builder.add_node("workers", workers_node)
    builder.add_node("done", done_node)

    # 시작점
    builder.add_edge(START, "supervisor")

    # supervisor 이후 필요하면 API별 정규화 노드를 거친 뒤 조건 분기
    route_source = "supervisor"
    if after_supervisor is not None:
        route_source = "after_supervisor"
        builder.add_node(route_source, after_supervisor)
        builder.add_edge("supervisor", route_source)

    builder.add_conditional_edges(
        route_source,
        route_after_supervisor,
        {
            "workers": "workers",
            "done": "done",
        },
    )

    # workers → done → END
    builder.add_edge("workers", "done")
    builder.add_edge("done", END)

    # MemorySaver: thread_id 별로 state를 메모리에 보관
    memory = MemorySaver()
    return builder.compile(checkpointer=memory)
