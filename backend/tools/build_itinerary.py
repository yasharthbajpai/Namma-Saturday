"""Tool 4 — Use Claude (via Bedrock) to arrange filtered places into a time-logical itinerary.

Two modes baked into one call:
- Normal: filtered places exist -> arrange them with reasoning
- Fallback: candidates_exhausted -> generate a city-specific "minimal chill day"
  using free/cheap public spots and home-based activities. More itinerary items
  in this mode so it doesn't feel empty.
"""

import json
import re
from models.domain import ParsedPreferences, ItineraryItem
from services.bedrock import invoke_claude, BedrockError


SYSTEM_PROMPT = (
    "You are a thoughtful Saturday planning assistant. "
    "Your job is to build the BEST possible itinerary within the given budget — "
    "not just any plan that fits, but the one that maximises enjoyment, mood fit, "
    "and variety for the money available. "
    "Prefer high-rated, well-matched places over cheaper but less fitting ones. "
    "If the budget is tight, be creative: mix a free outdoor spot with one good paid experience "
    "rather than cramming in mediocre paid stops. "
    "You are honest about trade-offs. You only respond with valid JSON in the exact schema requested."
)


USER_PROMPT_TEMPLATE = """BUDGET CONSTRAINT: The sum of all estimated_cost values MUST NOT exceed ₹{budget}.
Pick fewer stops or cheaper options if needed. Do not go over.

User preferences:
- City: {city}
- Hours available: {hours}
- Energy level: {energy}
- Novelty preference: {novelty}
- Mood (raw): {mood}
- Interests: {interests}
- Constraints: {constraints}

{candidates_block}

{instruction}

Return ONLY a valid JSON object in this exact shape:
{{
  "itinerary": [
    {{
      "time_slot": "10:00 AM",
      "place_name": "string",
      "activity": "string (what to do there, 1 sentence)",
      "duration_minutes": 60,
      "estimated_cost": 0,
      "reasoning": "string (why this fits the user — mention mood, interest, or trade-off)"
    }}
  ],
  "summary": "1-2 sentence overall pitch for the day",
  "trade_offs": ["string", "string"]
}}

Rules:
- Order stops logically by time of day (morning -> lunch -> afternoon -> evening).
- If energy is low, start lighter and slower.
- Fit within the available hours.
- If a candidate is borderline (has a trade_off note), include it only if it materially improves the day, and explain the trade-off in reasoning.
- Output JSON only. No prose before or after."""


NORMAL_INSTRUCTION = (
    "Build the BEST possible itinerary using ONLY the candidate places listed above. "
    "Choose the combination of 3-5 stops that maximises enjoyment and mood fit within the budget. "
    "Prefer high-rated, well-matched places. If budget is tight, mix a free stop "
    "(park, walk) with one or two good paid experiences rather than filling every slot "
    "with mediocre paid options. "
    "Give each stop a time slot, duration, and a clear reason why it fits this specific user."
)

FALLBACK_INSTRUCTION = (
    "No suitable places were found in our database for this user. "
    "Use your own knowledge of the city to suggest a realistic, personalised Saturday plan. "
    "Pick real, specific places (actual café names, parks, markets, venues) that exist in "
    "the city and genuinely match the user's interests, energy level, mood, and constraints "
    "listed above. Respect the budget — prefer free or low-cost options if the budget is tight. "
    "Aim for 4-5 stops so the day feels full. "
    "Mention in the summary and trade_offs that these suggestions come from general knowledge "
    "rather than live data, so availability and pricing should be verified."
)


def _candidates_block(approved: list, borderline: list) -> str:
    if not approved and not borderline:
        return "Candidate places: none."

    def _fmt(p):
        line = f"- {p.name} (types: {', '.join(p.types[:3]) or 'n/a'}, rating: {p.rating or 'n/a'}, est_cost: {int(p.estimated_cost)}, score: {round(p.score, 1)})"
        if p.trade_off:
            line += f"\n  trade_off: {p.trade_off}"
        return line

    parts = ["Approved candidates:"]
    parts += [_fmt(p) for p in approved] if approved else ["  (none)"]
    if borderline:
        parts.append("\nBorderline candidates (include only if they materially help):")
        parts += [_fmt(p) for p in borderline]
    return "\n".join(parts)


def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise


def _python_fallback_itinerary(prefs: ParsedPreferences, approved: list, borderline: list) -> dict:
    """Last-resort if Bedrock itself fails — just dump candidates into time slots."""
    candidates = approved + borderline
    times = ["10:00 AM", "12:30 PM", "3:00 PM", "5:30 PM"]
    items = []
    if not candidates:
        items = [
            {
                "time_slot": "10:00 AM",
                "place_name": f"A walk around {prefs.city}",
                "activity": "Take a slow walk in a nearby park or quiet neighbourhood",
                "duration_minutes": 60,
                "estimated_cost": 0,
                "reasoning": "Free, low-energy, resets the day.",
            },
            {
                "time_slot": "12:30 PM",
                "place_name": "A local cafe",
                "activity": "Lunch at a nearby cafe or local spot",
                "duration_minutes": 75,
                "estimated_cost": min(prefs.budget * 0.4, 500),
                "reasoning": "Keeps the budget low while still feeling like a Saturday.",
            },
            {
                "time_slot": "3:00 PM",
                "place_name": "Home time",
                "activity": "A book, a playlist, or a film you've been meaning to watch",
                "duration_minutes": 120,
                "estimated_cost": 0,
                "reasoning": "Sometimes the best Saturday is a quiet one.",
            },
        ]
    else:
        for i, place in enumerate(candidates[:4]):
            items.append({
                "time_slot": times[i] if i < len(times) else "Evening",
                "place_name": place.name,
                "activity": f"Spend time at {place.name}",
                "duration_minutes": 75,
                "estimated_cost": place.estimated_cost,
                "reasoning": place.trade_off or "Matches your interests and constraints.",
            })

    return {
        "itinerary": items,
        "summary": "A simple Saturday plan generated without the AI narrative service.",
        "trade_offs": ["Used a deterministic fallback because the reasoning service was unavailable."],
    }


async def build_itinerary(filter_result: dict, prefs: ParsedPreferences) -> dict:
    """Returns dict with itinerary, summary, trade_offs, used_fallback flag."""
    approved = filter_result.get("approved", [])
    borderline = filter_result.get("borderline", [])
    candidates_exhausted = filter_result.get("candidates_exhausted", False)

    instruction = FALLBACK_INSTRUCTION if candidates_exhausted else NORMAL_INSTRUCTION
    user_prompt = USER_PROMPT_TEMPLATE.format(
        city=prefs.city,
        hours=prefs.hours_available,
        energy=prefs.energy_level,
        novelty=prefs.novelty_preference,
        mood=prefs.raw_mood or "(not specified)",
        interests=", ".join(prefs.interests) or "(none)",
        constraints=", ".join(prefs.constraints) or "(none)",
        budget=int(prefs.budget),
        candidates_block=_candidates_block(approved, borderline),
        instruction=instruction,
    )

    try:
        raw_text = await invoke_claude(user_prompt, system=SYSTEM_PROMPT, max_tokens=2000)
        parsed = _extract_json(raw_text)
    except (BedrockError, json.JSONDecodeError, ValueError):
        result = _python_fallback_itinerary(prefs, approved, borderline)
        return {
            "itinerary": [ItineraryItem(**i) for i in result["itinerary"]],
            "summary": result["summary"],
            "trade_offs": result["trade_offs"],
            "used_fallback": True,
            "used_python_fallback": True,
            "candidates_exhausted": candidates_exhausted,
        }

    items_raw = parsed.get("itinerary", [])
    items: list[ItineraryItem] = []
    for it in items_raw:
        try:
            items.append(ItineraryItem(
                time_slot=str(it.get("time_slot", "")),
                place_name=str(it.get("place_name", "")),
                activity=str(it.get("activity", "")),
                duration_minutes=int(it.get("duration_minutes", 60)),
                estimated_cost=float(it.get("estimated_cost", 0) or 0),
                reasoning=str(it.get("reasoning", "")),
            ))
        except (ValueError, TypeError):
            continue

    return {
        "itinerary": items,
        "summary": str(parsed.get("summary", "")),
        "trade_offs": [str(t) for t in parsed.get("trade_offs", [])],
        "used_fallback": candidates_exhausted,
        "used_python_fallback": False,
        "candidates_exhausted": candidates_exhausted,
    }
