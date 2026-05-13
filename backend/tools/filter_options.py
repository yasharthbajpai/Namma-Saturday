"""Tool 3 — Score and filter candidate places against budget + constraints.

Pure Python. Three buckets after running:
- approved: clearly fits everything (score >= 7)
- borderline: passes most constraints but has trade-offs (score 4-6.99)
- rejected: drop completely

Approved + borderline are returned to Tool 4 with a trade_off note on borderline
items so Claude can explain the trade-off in natural language.
"""

from models.domain import ParsedPreferences, Place


NON_VEG_KEYWORDS = {"meat", "barbecue", "steak_house", "seafood"}
CROWDED_TYPES = {"night_club", "shopping_mall", "amusement_park", "tourist_attraction"}


def _per_stop_budget(prefs: ParsedPreferences) -> float:
    stops = max(2, int(prefs.hours_available // 1.5))
    return prefs.budget / stops


def _violates_constraints(place: Place, constraints: list[str]) -> tuple[bool, str | None]:
    """Returns (hard_fail, soft_warning)."""
    type_str = " ".join(place.types).lower()
    name_lower = place.name.lower()

    for c in constraints:
        if "veg" in c:
            if any(kw in type_str for kw in NON_VEG_KEYWORDS):
                return True, None
            if "meat" in name_lower or "barbecue" in name_lower or "kebab" in name_lower:
                return True, None
        if "avoid crowded" in c or "no crowd" in c or "not crowded" in c:
            if place.user_rating_count and place.user_rating_count > 30000:
                return False, "Popular spot — may get crowded"
            if any(t in CROWDED_TYPES for t in place.types):
                return False, "Tends to be a crowded venue"
        if "quiet" in c:
            if place.user_rating_count and place.user_rating_count > 20000:
                return False, "Quite popular, may not feel as quiet"

    return False, None


def _score_place(place: Place, prefs: ParsedPreferences) -> tuple[float, str | None]:
    score = 5.0
    trade_off: str | None = None

    if place.rating is not None:
        score += (place.rating - 3.5) * 1.5

    if place.user_rating_count:
        if place.user_rating_count > 500:
            score += 0.5
        if place.user_rating_count > 5000:
            score += 0.5

    per_stop_budget = _per_stop_budget(prefs)
    if place.estimated_cost <= per_stop_budget:
        score += 1.5
    elif place.estimated_cost <= per_stop_budget * 1.3:
        score -= 0.5
        trade_off = (
            f"Slightly over per-stop budget (est. ~{int(place.estimated_cost)} vs ~{int(per_stop_budget)})"
        )
    else:
        score -= 3.0
        trade_off = (
            f"Significantly over per-stop budget (est. ~{int(place.estimated_cost)} vs ~{int(per_stop_budget)})"
        )

    type_str = " ".join(place.types).lower()
    name_lower = place.name.lower()
    for interest in prefs.interests:
        if interest in type_str or interest in name_lower:
            score += 0.5

    if prefs.energy_level == "low" and any(t in CROWDED_TYPES for t in place.types):
        score -= 1.0
    if prefs.energy_level == "high" and "park" in type_str:
        score -= 0.3

    score = max(0.0, min(10.0, score))
    return score, trade_off


def filter_options(places: list[Place], prefs: ParsedPreferences) -> dict:
    approved: list[Place] = []
    borderline: list[Place] = []
    rejected_count = 0

    for place in places:
        hard_fail, soft_warning = _violates_constraints(place, prefs.constraints)
        if hard_fail:
            rejected_count += 1
            continue

        score, cost_trade_off = _score_place(place, prefs)
        place.score = score

        combined_trade_offs = [t for t in [soft_warning, cost_trade_off] if t]
        if combined_trade_offs:
            place.trade_off = "; ".join(combined_trade_offs)

        if score >= 7.0:
            approved.append(place)
        elif score >= 4.0:
            place.is_borderline = True
            borderline.append(place)
        else:
            rejected_count += 1

    approved.sort(key=lambda p: p.score, reverse=True)
    borderline.sort(key=lambda p: p.score, reverse=True)

    return {
        "approved": approved[:8],
        "borderline": borderline[:4],
        "rejected_count": rejected_count,
        "candidates_exhausted": (len(approved) + len(borderline)) == 0,
    }
