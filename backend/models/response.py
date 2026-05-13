from typing import Literal
from pydantic import BaseModel, Field
from models.domain import ItineraryItem


PlanStatus = Literal["ok", "needs_clarification", "fallback"]


class ToolTrace(BaseModel):
    tool_name: str
    input_summary: str = ""
    output_summary: str = ""
    duration_ms: float = 0
    used_fallback: bool = False
    error: str = ""


class PlanResponse(BaseModel):
    status: PlanStatus = "ok"
    itinerary: list[ItineraryItem] = Field(default_factory=list)
    total_cost: float = 0
    summary: str = ""
    trade_offs: list[str] = Field(default_factory=list)
    fallback_used: bool = False
    clarification_questions: list[str] = Field(default_factory=list)
    trace: list[ToolTrace] = Field(default_factory=list)
