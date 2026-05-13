from typing import Optional, Literal
from pydantic import BaseModel, Field


EnergyLevel = Literal["low", "medium", "high"]
NoveltyPreference = Literal["low", "medium", "high"]


class ParsedPreferences(BaseModel):
    city: str
    budget: float
    hours_available: float
    energy_level: EnergyLevel = "medium"
    novelty_preference: NoveltyPreference = "medium"
    interests: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    raw_mood: str = ""
    needs_clarification: bool = False
    clarification_questions: list[str] = Field(default_factory=list)


class Place(BaseModel):
    name: str
    types: list[str] = Field(default_factory=list)
    rating: Optional[float] = None
    user_rating_count: Optional[int] = None
    price_level: Optional[int] = None
    address: str = ""
    place_id: str = ""
    maps_url: str = ""
    estimated_cost: float = 0
    score: float = 0
    trade_off: Optional[str] = None
    is_borderline: bool = False
    source: str = "google_places"


class ItineraryItem(BaseModel):
    time_slot: str
    place_name: str
    activity: str
    duration_minutes: int = 60
    estimated_cost: float = 0
    reasoning: str = ""
    maps_url: str = ""
