"""
Pydantic models for API request/response validation.
"""

from typing import Literal

from pydantic import BaseModel, Field


class PropertyItem(BaseModel):
    """Single property item in search results."""

    id: int = Field(description="Property ID")
    title: str = Field(description="Property title")
    city: str = Field(description="City")
    price: int = Field(description="Price")
    layout: str = Field(description="Layout (e.g., '1K', '1DK')")
    walk_min: int = Field(description="Walking minutes to station")
    pet: bool = Field(description="Pet allowed")
    me5_score: float = Field(default=0.0, ge=0.0, le=1.0, description="ME5 embedding similarity score")

    model_config = {"title": "PropertyItem"}


class SearchParams(BaseModel):
    """Query parameters for the /search endpoint."""

    q: str = Field(default="", max_length=500, description="Search query")
    user_id: int | None = Field(default=None, description="User ID")
    city: str | None = Field(default=None, max_length=100, description="City filter")
    layout: str | None = Field(default=None, description="Layout filter")
    price_lte: int | None = Field(default=None, ge=0, description="Max price")
    pet: bool | None = Field(default=None, description="Pet allowed filter")
    walk_min: int | None = Field(default=None, ge=0, description="Walk minutes")
    limit: int = Field(default=20, ge=1, le=100, description="Result limit")
    candidate_limit: int = Field(default=100, ge=1, le=200, description="Candidate limit for reranking")

    model_config = {"title": "SearchParams"}


class FeedbackRequest(BaseModel):
    """Request body for the /feedback endpoint."""

    user_id: int | None = Field(default=None, description="User ID")
    property_id: int = Field(gt=0, description="Property ID")
    action: Literal["click", "favorite", "inquiry"] = Field(description="Feedback action")
    search_log_id: int | None = Field(default=None, gt=0, description="Search log ID")

    model_config = {"title": "FeedbackRequest"}


class SearchResult(BaseModel):
    """Response model for search results."""

    items: list[PropertyItem] = Field(description="Search result items")
    count: int = Field(ge=0, description="Total result count")

    model_config = {"title": "SearchResult"}


class FeedbackResponse(BaseModel):
    """Response model for feedback endpoint."""

    status: str = Field(description="Operation status")
    message: str = Field(description="Response message")

    model_config = {"title": "FeedbackResponse"}
