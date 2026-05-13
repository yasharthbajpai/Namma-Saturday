"""Agent orchestrator — runs the 5-tool pipeline sequentially and collects a trace.

Pipeline:
  Tool 1 parse_preferences      (pure Python)
  Tool 2 get_options            (Google Places, with hardcoded fallback)
  Tool 3 filter_options         (pure Python)
  Tool 4 build_itinerary        (Bedrock Claude, with Python fallback)
  Tool 5 cost_check             (pure Python)

If Tool 1 flags `needs_clarification`, the pipeline short-circuits and returns
clarifying questions instead of running 2-5.

Streaming:
  run_agent_stream() activates an SSE event queue via contextvars so tool_span
  automatically emits "thinking" and "trace" events without any changes to the
  tool call sites.
"""

import logging
from models.request import UserInput
from models.response import PlanResponse, ToolTrace
from core.pipeline import tool_span
from tools.parse_preferences import parse_preferences
from tools.get_options import get_options
from tools.filter_options import filter_options
from tools.build_itinerary import build_itinerary
from tools.cost_check import cost_check

logger = logging.getLogger("agent")


async def run_agent(user_input: UserInput) -> PlanResponse:
    interests = ", ".join(user_input.interests) or "—"
    constraints = ", ".join(user_input.constraints) or "—"
    logger.info(f"AGENT RUN  {user_input.city} · ₹{user_input.budget} · {user_input.available_time}")
    logger.info(f"  mood: {user_input.mood}")
    logger.info(f"  interests: {interests}  ·  constraints: {constraints}")

    trace: list[ToolTrace] = []


    #########################################################
    # Step 1 — turn free-text input into structured preferences
    #########################################################
    async with tool_span(trace, "parse_preferences",
                         f"city={user_input.city!r}, budget={user_input.budget}, "
                         f"time={user_input.available_time!r}",
                         step=1,
                         thinking="Reading your preferences...") as span:
        prefs = parse_preferences(user_input)
        span.output = (f"energy={prefs.energy_level}, hours={prefs.hours_available}, "
                       f"novelty={prefs.novelty_preference}, clarify={prefs.needs_clarification}")

    if prefs.needs_clarification:
        logger.info(f"CLARIFY  {prefs.clarification_questions}")
        return PlanResponse(
            status="needs_clarification",
            clarification_questions=prefs.clarification_questions,
            summary="Need a couple more details before planning your Saturday.",
            trace=trace,
        )


    #########################################################
    # Step 2 — fetch candidate places from Google Places (falls back to curated list on failure)
    #########################################################
    places_used_fallback = False
    try:
        async with tool_span(trace, "get_options",
                             f"city={prefs.city}, interests={prefs.interests}",
                             step=2,
                             thinking=f"Searching for places in {prefs.city}...") as span:
            candidates, places_used_fallback = await get_options(prefs)
            span.output = f"{len(candidates)} candidates"
            span.used_fallback = places_used_fallback
    except Exception:
        candidates = []
        places_used_fallback = True


    #########################################################
    # Step 3 — score and filter candidates against budget + constraints
    #########################################################
    async with tool_span(trace, "filter_options",
                         f"{len(candidates)} candidates, budget={prefs.budget}, "
                         f"constraints={prefs.constraints}",
                         step=3,
                         thinking="Filtering places against your budget and constraints...") as span:
        filter_result = filter_options(candidates, prefs)
        span.output = (f"approved={len(filter_result['approved'])}, "
                       f"borderline={len(filter_result['borderline'])}, "
                       f"rejected={filter_result['rejected_count']}")

    #########################################################
    # Step 4 — Claude arranges filtered places into a time-logical itinerary with reasoning
    #########################################################
    try:
        async with tool_span(trace, "build_itinerary",
                             f"approved={len(filter_result['approved'])}, "
                             f"borderline={len(filter_result['borderline'])}, "
                             f"fallback_mode={filter_result['candidates_exhausted']}",
                             step=4,
                             thinking="Building your itinerary...") as span:
            itinerary_result = await build_itinerary(filter_result, prefs)
            span.output = (f"{len(itinerary_result['itinerary'])} items, "
                           f"python_fallback={itinerary_result['used_python_fallback']}")
            span.used_fallback = (itinerary_result["used_fallback"]
                                  or itinerary_result["used_python_fallback"])
    except Exception:
        itinerary_result = {
            "itinerary": [],
            "summary": "Couldn't generate an itinerary — agent failed unexpectedly.",
            "trade_offs": [],
            "used_fallback": True,
            "used_python_fallback": True,
            "candidates_exhausted": True,
        }

    #########################################################
    # Step 5 — validate total cost, trim if over budget
    #########################################################
    async with tool_span(trace, "cost_check",
                         f"{len(itinerary_result['itinerary'])} items, "
                         f"budget={prefs.budget}",
                         step=5,
                         thinking="Checking costs and finalising your plan...") as span:
        cost_result = cost_check(itinerary_result["itinerary"], prefs)
        span.output = (f"{len(cost_result['itinerary'])} items · "
                       f"₹{cost_result['total_cost']} · budget_ok={cost_result['budget_ok']}")

    trade_offs = list(itinerary_result.get("trade_offs", []))
    trade_offs.extend(cost_result.get("extra_trade_offs", []))
    if places_used_fallback:
        trade_offs.append("Used a curated fallback list — live place data was unavailable.")

    fallback_used = (
        places_used_fallback
        or itinerary_result.get("used_fallback", False)
        or itinerary_result.get("used_python_fallback", False)
    )
    status = "fallback" if fallback_used else "ok"

    logger.info(f"DONE  status={status} · items={len(cost_result['itinerary'])} · ₹{cost_result['total_cost']}")

    return PlanResponse(
        status=status,
        itinerary=cost_result["itinerary"],
        total_cost=cost_result["total_cost"],
        summary=itinerary_result.get("summary", ""),
        trade_offs=trade_offs,
        fallback_used=fallback_used,
        trace=trace,
    )