"""Legacy Foodie worker aliases backed by Restaurant."""

from .agent import (
    recommend_nearby_foods_for_places,
    run_foodie_agent,
    run_foodie_agent_for_state,
    run_nearby_foodie_agent,
)

__all__ = [
    "recommend_nearby_foods_for_places",
    "run_foodie_agent",
    "run_foodie_agent_for_state",
    "run_nearby_foodie_agent",
]
