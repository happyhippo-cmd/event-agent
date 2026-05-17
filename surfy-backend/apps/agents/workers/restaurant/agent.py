"""Restaurant worker aliases backed by the Foodie implementation."""

from __future__ import annotations

from typing import Any

from apps.agents.state import AGENT_FOODIE, AGENT_RESTAURANT, KDiveState
from apps.agents.workers.foodie.agent import (
    DEFAULT_TOP_K,
    recommend_nearby_foods_for_places,
    run_foodie_agent,
    run_nearby_foodie_agent,
)

def run_restaurant_agent(
    taste_context: dict[str, Any],
    top_k: int = DEFAULT_TOP_K,
) -> dict[str, Any]:
    return run_foodie_agent(taste_context=taste_context, top_k=top_k)


def run_restaurant_agent_for_state(
    state: KDiveState,
    top_k: int = DEFAULT_TOP_K,
) -> KDiveState:
    target_agents = state.get("target_agents", [])
    if AGENT_RESTAURANT not in target_agents and AGENT_FOODIE not in target_agents:
        return state

    result = run_restaurant_agent(
        taste_context=state.get("taste_context", {}),
        top_k=top_k,
    )
    state["foodie_result"] = result
    state["restaurant_result"] = result
    return state


def run_nearby_restaurant_agent(
    anchors: list[dict[str, Any]],
    taste_context: dict[str, Any],
    top_k: int = DEFAULT_TOP_K,
    radius_km: float = 2.0,
) -> dict[str, Any]:
    return run_nearby_foodie_agent(
        anchors=anchors,
        taste_context=taste_context,
        top_k=top_k,
        radius_km=radius_km,
    )


run = run_restaurant_agent
