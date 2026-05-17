"""Restaurant schema aliases backed by the Foodie implementation."""

from apps.agents.workers.foodie.schemas import FoodieAgentResult, FoodieCandidate

RestaurantAgentResult = FoodieAgentResult
RestaurantCandidate = FoodieCandidate

__all__ = [
    "FoodieAgentResult",
    "FoodieCandidate",
    "RestaurantAgentResult",
    "RestaurantCandidate",
]
