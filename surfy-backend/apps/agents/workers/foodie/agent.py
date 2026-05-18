"""Legacy Foodie aliases backed by the Restaurant worker."""

from __future__ import annotations

from apps.agents.workers.restaurant.agent import (
    DEFAULT_TOP_K,
    build_restaurant_query,
    recommend_nearby_foods_for_places,
    run_nearby_restaurant_agent,
    run_restaurant_agent,
    run_restaurant_agent_for_state,
)

build_foodie_query = build_restaurant_query
run_foodie_agent = run_restaurant_agent
run_foodie_agent_for_state = run_restaurant_agent_for_state
run_nearby_foodie_agent = run_nearby_restaurant_agent
run = run_foodie_agent
