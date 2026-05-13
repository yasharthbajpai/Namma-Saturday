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

import time
import logging
from models.request import UserInput
from models.response import PlanResponse, ToolTrace
from tools.parse_preferences import parse_preferences
from tools.get_options import get_options
from tools.filter_options import filter_options
from tools.build_itinerary import build_itinerary
from tools.cost_check import cost_check

logger = logging.getLogger("agent")


def _ms_since(start: float) -> float:
    return round((time.perf_counter() - start) * 1000, 1)


async def run_agent(user_input: UserInput) -> PlanResponse:
    logger.info("=" * 60)
    logger.info("AGENT RUN STARTED")
    logger.info(f"  city={user_input.city!r}, budget={user_input.budget}, "
                f"time={user_input.available_time!r}")
    logger.info(f"  mood={user_input.mood!r}")
    logger.info(f"  interests={user_input.interests}, constraints={user_input.constraints}")
    logger.info("-" * 60)

    trace: list[ToolTrace] = []

    t0 = time.perf_counter()
    prefs = parse_preferences(user_input)
    logger.info(f"[Tool 1] parse_preferences -> energy={prefs.energy_level}, "
                f"hours={prefs.hours_available}, novelty={prefs.novelty_preference}, "
                f"needs_clarification={prefs.needs_clarification} ({_ms_since(t0)}ms)")
    trace.append(ToolTrace(
        tool_name="parse_preferences",
        input_summary=(
            f"city='{user_input.city}', budget={user_input.budget}, "
            f"time='{user_input.available_time}', mood='{user_input.mood}', "
            f"interests={user_input.interests}, constraints={user_input.constraints}"
        ),
        output_summary=(
            f"city={prefs.city}, hours={prefs.hours_available}, energy={prefs.energy_level}, "
            f"novelty={prefs.novelty_preference}, needs_clarification={prefs.needs_clarification}"
        ),
        duration_ms=_ms_since(t0),
    ))

    if prefs.needs_clarification:
        logger.info(f"  -> Short-circuiting: {prefs.clarification_questions}")
        logger.info("AGENT RUN ENDED (needs_clarification)")
        logger.info("=" * 60)
        return PlanResponse(
            status="needs_clarification",
            clarification_questions=prefs.clarification_questions,
            summary="Need a couple more details before planning your Saturday.",
            trace=trace,
        )

    t0 = time.perf_counter()
    try:
        candidates, places_used_fallback = await get_options(prefs)
        logger.info(f"[Tool 2] get_options -> {len(candidates)} candidates, "
                    f"fallback={places_used_fallback} ({_ms_since(t0)}ms)")
        trace.append(ToolTrace(
            tool_name="get_options",
            input_summary=f"city={prefs.city}, interests={prefs.interests}",
            output_summary=f"{len(candidates)} candidate places returned",
            duration_ms=_ms_since(t0),
            used_fallback=places_used_fallback,
        ))
    except Exception as exc:
        candidates = []
        places_used_fallback = True
        logger.error(f"[Tool 2] get_options -> ERROR: {exc} ({_ms_since(t0)}ms)")
        trace.append(ToolTrace(
            tool_name="get_options",
            input_summary=f"city={prefs.city}",
            output_summary="error — using empty candidate set",
            duration_ms=_ms_since(t0),
            used_fallback=True,
            error=str(exc),
        ))

    t0 = time.perf_counter()
    filter_result = filter_options(candidates, prefs)
    logger.info(f"[Tool 3] filter_options -> approved={len(filter_result['approved'])}, "
                f"borderline={len(filter_result['borderline'])}, "
                f"rejected={filter_result['rejected_count']}, "
                f"exhausted={filter_result['candidates_exhausted']} ({_ms_since(t0)}ms)")
    trace.append(ToolTrace(
        tool_name="filter_options",
        input_summary=f"{len(candidates)} candidates, budget={prefs.budget}, constraints={prefs.constraints}",
        output_summary=(
            f"approved={len(filter_result['approved'])}, borderline={len(filter_result['borderline'])}, "
            f"rejected={filter_result['rejected_count']}, exhausted={filter_result['candidates_exhausted']}"
        ),
        duration_ms=_ms_since(t0),
    ))

    t0 = time.perf_counter()
    try:
        itinerary_result = await build_itinerary(filter_result, prefs)
        logger.info(f"[Tool 4] build_itinerary -> {len(itinerary_result['itinerary'])} items, "
                    f"used_fallback={itinerary_result['used_fallback']}, "
                    f"python_fallback={itinerary_result['used_python_fallback']} ({_ms_since(t0)}ms)")
        trace.append(ToolTrace(
            tool_name="build_itinerary",
            input_summary=(
                f"approved={len(filter_result['approved'])}, borderline={len(filter_result['borderline'])}, "
                f"fallback_mode={filter_result['candidates_exhausted']}"
            ),
            output_summary=(
                f"{len(itinerary_result['itinerary'])} items, "
                f"used_fallback={itinerary_result['used_fallback']}, "
                f"python_fallback={itinerary_result['used_python_fallback']}"
            ),
            duration_ms=_ms_since(t0),
            used_fallback=itinerary_result["used_fallback"] or itinerary_result["used_python_fallback"],
        ))
    except Exception as exc:
        logger.error(f"[Tool 4] build_itinerary -> ERROR: {exc} ({_ms_since(t0)}ms)")
        itinerary_result = {
            "itinerary": [],
            "summary": "Couldn't generate an itinerary — agent failed unexpectedly.",
            "trade_offs": [],
            "used_fallback": True,
            "used_python_fallback": True,
            "candidates_exhausted": True,
        }
        trace.append(ToolTrace(
            tool_name="build_itinerary",
            input_summary="",
            output_summary="error",
            duration_ms=_ms_since(t0),
            used_fallback=True,
            error=str(exc),
        ))

    t0 = time.perf_counter()
    cost_result = cost_check(itinerary_result["itinerary"], prefs)
    logger.info(f"[Tool 5] cost_check -> {len(cost_result['itinerary'])} items, "
                f"total={cost_result['total_cost']}, budget_ok={cost_result['budget_ok']} ({_ms_since(t0)}ms)")
    trace.append(ToolTrace(
        tool_name="cost_check",
        input_summary=f"{len(itinerary_result['itinerary'])} items, budget={prefs.budget}",
        output_summary=(
            f"final={len(cost_result['itinerary'])} items, total={cost_result['total_cost']}, "
            f"budget_ok={cost_result['budget_ok']}"
        ),
        duration_ms=_ms_since(t0),
    ))

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
    logger.info(f"AGENT RUN COMPLETED -> status={status}, "
                f"items={len(cost_result['itinerary'])}, total_cost={cost_result['total_cost']}")
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
