"""Agent orchestrator — runs the 5-tool pipeline sequentially and collects a trace.

Pipeline:
  Tool 1 parse_preferences      (pure Python)
  Tool 2 get_options            (Google Places, with hardcoded fallback)
  Tool 3 filter_options         (pure Python)
  Tool 4 build_itinerary        (Bedrock Claude, with Python fallback)
  Tool 5 cost_check             (pure Python)

If Tool 1 flags `needs_clarification`, the pipeline short-circuits and returns
clarifying questions instead of running 2-5.
"""

import logging
from models.request import UserInput
from models.response import PlanResponse, ToolTrace
from core.logging_config import tool_span
from tools.parse_preferences import parse_preferences
from tools.get_options import get_options
from tools.filter_options import filter_options
from tools.build_itinerary import build_itinerary
from tools.cost_check import cost_check

logger = logging.getLogger("agent")


async def run_agent(user_input: UserInput) -> PlanResponse:
    logger.info("=" * 60)
    logger.info(
        f"AGENT RUN | city={user_input.city!r} budget={user_input.budget} "
        f"time={user_input.available_time!r} mood={user_input.mood!r}"
    )
    logger.info(f"  interests={user_input.interests} constraints={user_input.constraints}")
    logger.info("-" * 60)

    trace: list[ToolTrace] = []

    # ── Tool 1: Parse ────────────────────────────────────────────
    async with tool_span(trace, "parse_preferences",
                         f"city={user_input.city!r}, budget={user_input.budget}, "
                         f"time={user_input.available_time!r}") as span:
        prefs = parse_preferences(user_input)
        span.output = (f"energy={prefs.energy_level}, hours={prefs.hours_available}, "
                       f"novelty={prefs.novelty_preference}, clarify={prefs.needs_clarification}")

    if prefs.needs_clarification:
        logger.info(f"  -> clarify: {prefs.clarification_questions}")
        logger.info("AGENT RUN ENDED (needs_clarification)")
        logger.info("=" * 60)
        return PlanResponse(
            status="needs_clarification",
            clarification_questions=prefs.clarification_questions,
            summary="Need a couple more details before planning your Saturday.",
            trace=trace,
        )

    # ── Tool 2: Get options ──────────────────────────────────────
    places_used_fallback = False
    try:
        async with tool_span(trace, "get_options",
                             f"city={prefs.city}, interests={prefs.interests}") as span:
            candidates, places_used_fallback = await get_options(prefs)
            span.output = f"{len(candidates)} candidates"
            span.used_fallback = places_used_fallback
    except Exception:
        candidates = []
        places_used_fallback = True

    # ── Tool 3: Filter ───────────────────────────────────────────
    async with tool_span(trace, "filter_options",
                         f"{len(candidates)} candidates, budget={prefs.budget}, "
                         f"constraints={prefs.constraints}") as span:
        filter_result = filter_options(candidates, prefs)
        span.output = (f"approved={len(filter_result['approved'])}, "
                       f"borderline={len(filter_result['borderline'])}, "
                       f"rejected={filter_result['rejected_count']}, "
                       f"exhausted={filter_result['candidates_exhausted']}")

    # ── Tool 4: Build itinerary ──────────────────────────────────
    try:
        async with tool_span(trace, "build_itinerary",
                             f"approved={len(filter_result['approved'])}, "
                             f"borderline={len(filter_result['borderline'])}, "
                             f"fallback_mode={filter_result['candidates_exhausted']}") as span:
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

    # ── Tool 5: Cost check ───────────────────────────────────────
    async with tool_span(trace, "cost_check",
                         f"{len(itinerary_result['itinerary'])} items, "
                         f"budget={prefs.budget}") as span:
        cost_result = cost_check(itinerary_result["itinerary"], prefs)
        span.output = (f"{len(cost_result['itinerary'])} items, "
                       f"total={cost_result['total_cost']}, budget_ok={cost_result['budget_ok']}")

    # ── Finalise ─────────────────────────────────────────────────
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

    logger.info("-" * 60)
    logger.info(f"AGENT RUN COMPLETED | status={status} "
                f"items={len(cost_result['itinerary'])} total=₹{cost_result['total_cost']}")
    logger.info("=" * 60)

    return PlanResponse(
        status=status,
        itinerary=cost_result["itinerary"],
        total_cost=cost_result["total_cost"],
        summary=itinerary_result.get("summary", ""),
        trade_offs=trade_offs,
        fallback_used=fallback_used,
        trace=trace,
    )
