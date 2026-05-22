"""
Event Worker Agent — LangGraph 그래프 정의

[그래프 구조]
        [START]
           ↓
       prepare        ← taste_context 분해
           ↓
        search        ← 키워드 + 벡터 검색 병합
           ↓
        filter        ← 지역/장르 하드 필터
           ↓
    [후보 있나?]      ← 조건 분기
     /        \
   없음        있음
    ↓           ↓
  relax       curate    ← LLM 큐레이션
    ↓           ↓
  curate     format    ← 최종 응답 포맷
    ↓           ↓
  format       END
    ↓
   END

[설계 의도]
- 노드 함수는 nodes.py 에 분리 (그래프 정의와 노드 구현 분리)
- 외부 진입점은 run_event_graph(query, taste_context) 하나
- 기존 agent.py 의 run_event_agent() 와 입출력 동일 (교체 쉬움)
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import StateGraph, START, END

from .agent import DEFAULT_EVENT_TOP_K
from .nodes import (
    EventGraphState,
    prepare_node,
    search_node,
    filter_node,
    relax_node,
    curate_node,
    format_node,
    route_after_filter,
)


# ============================================================
# 그래프 빌드
# ============================================================


def build_event_graph():
    """이벤트 에이전트 그래프를 빌드해 컴파일된 객체를 반환."""
    graph = StateGraph(EventGraphState)

    # 1. 노드 등록
    graph.add_node("prepare", prepare_node)
    graph.add_node("search", search_node)
    graph.add_node("filter", filter_node)
    graph.add_node("relax", relax_node)
    graph.add_node("curate", curate_node)
    graph.add_node("format", format_node)

    # 2. 선형 엣지: START → prepare → search → filter
    graph.add_edge(START, "prepare")
    graph.add_edge("prepare", "search")
    graph.add_edge("search", "filter")

    # 3. 조건 분기: filter → (curate | relax | format)
    #    - 후보 있으면 바로 curate
    #    - 후보 없으면 relax 로 가서 다시 시도
    #    - 에러로 result 가 이미 있으면 format 으로 직행
    graph.add_conditional_edges(
        "filter",
        route_after_filter,
        {
            "curate": "curate",
            "relax": "relax",
            "format": "format",
        },
    )

    # 4. relax 후엔 항상 curate 로 진입 (curate_node 가 candidates 0건도 처리)
    graph.add_edge("relax", "curate")

    # 5. curate → format → END
    graph.add_edge("curate", "format")
    graph.add_edge("format", END)

    return graph.compile()


# 모듈 로드 시 1회만 컴파일 (재사용)
_compiled_graph = None


def get_compiled_graph():
    """컴파일된 그래프를 싱글턴으로 반환."""
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_event_graph()
    return _compiled_graph


# ============================================================
# 외부 진입점 — 기존 run_event_agent() 와 동일한 시그니처
# ============================================================


def run_event_graph(
    query: str,
    taste_context: dict[str, Any] | None = None,
    history: list[dict[str, str]] | None = None,
    top_k: int = DEFAULT_EVENT_TOP_K,
) -> dict[str, Any]:
    """LangGraph 버전 이벤트 에이전트 실행 함수.

    기존 run_event_agent() 와 입출력이 동일하다.
    """
    initial_state: EventGraphState = {
        "query": query,
        "taste_context": taste_context or {},
        "history": history or [],
        "top_k": top_k,
    }
    final_state = get_compiled_graph().invoke(initial_state)
    return final_state.get("result") or {
        "status": "error",
        "message": "그래프 실행이 결과 없이 종료됐어요.",
        "recommended_events": [],
    }
