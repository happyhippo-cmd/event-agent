from __future__ import annotations

from pydantic import BaseModel, Field


class FoodieCandidate(BaseModel):
    """A place candidate returned from the enriched-place vector store."""

    kakao_place_id: str
    name: str
    category: str
    gu: str
    address: str
    lat: float | None = None
    lng: float | None = None
    rating: float | None = None
    review_count: int | None = None
    price_level: int | None = None
    michelin_stars: int = 0
    is_bib_gourmand: bool = False
    mood_tags: dict = Field(default_factory=dict)
    similarity_score: float = Field(ge=0.0, le=1.0)
    matched_preferences: list[str] = Field(default_factory=list)
    ranking_basis: str = ""
    curation: str = ""


class FoodieAgentResult(BaseModel):
    """Foodie worker output stored in KDiveState['foodie_result']."""

    status: str
    query: str
    candidates: list[FoodieCandidate] = Field(default_factory=list)
    message: str = ""
