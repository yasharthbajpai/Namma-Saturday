"""Tool 1 — Parse free-text or partial user input into structured preferences.

Pure Python. No external API calls. If critical info is missing, flags the
preferences as needing clarification with hardcoded questions for the frontend.
"""

import re
from models.request import UserInput
from models.domain import ParsedPreferences


LOW_ENERGY_KEYWORDS = ["tired", "exhausted", "drained", "chill", "relax", "lazy", "low energy", "calm", "quiet", "rest"]
HIGH_ENERGY_KEYWORDS = ["energetic", "adventurous", "active", "pumped", "excited", "lively", "buzzing", "high energy"]
HIGH_NOVELTY_KEYWORDS = ["new", "different", "explore", "try", "adventure", "unique", "novel", "surprise"]
LOW_NOVELTY_KEYWORDS = ["usual", "familiar", "comfort", "favourite", "favorite", "routine"]


def _parse_hours(time_str: str) -> float:
    """Extract a float number of hours from free text like '4 hours', '3-4 hrs', 'half day'."""
    if not time_str:
        return 0.0

    text = time_str.lower().strip()

    if "full day" in text or "whole day" in text or "all day" in text:
        return 8.0
    if "half day" in text:
        return 4.0
    if "evening" in text:
        return 3.0
    if "morning" in text:
        return 3.0
    if "afternoon" in text:
        return 3.0

    match = re.search(r"(\d+(?:\.\d+)?)\s*(?:-\s*(\d+(?:\.\d+)?))?\s*(?:hour|hr|h\b)", text)
    if match:
        low = float(match.group(1))
        high = float(match.group(2)) if match.group(2) else low
        return (low + high) / 2

    match = re.search(r"(\d+(?:\.\d+)?)", text)
    if match:
        return float(match.group(1))

    return 0.0


def _infer_energy(mood: str) -> str:
    text = mood.lower()
    if any(kw in text for kw in LOW_ENERGY_KEYWORDS):
        return "low"
    if any(kw in text for kw in HIGH_ENERGY_KEYWORDS):
        return "high"
    return "medium"


def _infer_novelty(mood: str) -> str:
    text = mood.lower()
    if any(kw in text for kw in HIGH_NOVELTY_KEYWORDS):
        return "high"
    if any(kw in text for kw in LOW_NOVELTY_KEYWORDS):
        return "low"
    return "medium"


def _is_vague(text: str) -> bool:
    if not text:
        return True
    vague_tokens = {"sometime", "not sure", "dunno", "whatever", "anything", "idk", "maybe"}
    return text.lower().strip() in vague_tokens


def parse_preferences(user_input: UserInput) -> ParsedPreferences:
    questions: list[str] = []

    city = user_input.city.strip()
    if not city:
        questions.append("Which city are you planning your Saturday in?")

    hours = _parse_hours(user_input.available_time)
    if hours <= 0 or _is_vague(user_input.available_time):
        questions.append("Roughly how many hours do you have free — 2-3, 4-5, or a full day?")

    budget = float(user_input.budget) if user_input.budget else 0.0
    if budget <= 0:
        questions.append("What's your rough budget for the day (in your local currency)?")

    energy = _infer_energy(user_input.mood)
    novelty = _infer_novelty(user_input.mood)

    interests = [i.strip().lower() for i in user_input.interests if i.strip()]
    constraints = [c.strip().lower() for c in user_input.constraints if c.strip()]

    needs_clarification = len(questions) > 0

    return ParsedPreferences(
        city=city,
        budget=budget,
        hours_available=hours,
        energy_level=energy,
        novelty_preference=novelty,
        interests=interests if needs_clarification else (interests or ["food", "walks"]),
        constraints=constraints,
        raw_mood=user_input.mood,
        needs_clarification=needs_clarification,
        clarification_questions=questions[:2],
    )
