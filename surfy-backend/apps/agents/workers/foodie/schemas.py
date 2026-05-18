"""Legacy Foodie schema aliases backed by Restaurant."""

from apps.agents.workers.restaurant.schemas import (
    RestaurantAgentResult,
    RestaurantCandidate,
)

FoodieAgentResult = RestaurantAgentResult
FoodieCandidate = RestaurantCandidate

__all__ = [
    "FoodieAgentResult",
    "FoodieCandidate",
    "RestaurantAgentResult",
    "RestaurantCandidate",
]
