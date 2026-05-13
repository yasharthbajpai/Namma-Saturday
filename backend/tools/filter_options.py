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
CROWDED_TYPES    = {"night_club", "shopping_mall", "amusement_park", "tourist_attraction"}

MAX_APPROVED   = 25   # max candidates passed to Tool 4 from the approved bucket
MAX_BORDERLINE = 10  # max candidates passed to Tool 4 from the borderline bucket


def _per_stop_budget(prefs: ParsedPreferences) -> float:
    stops = max(2, int(prefs.hours_available // 1.5))
    return prefs.budget / stops


def _violates_constraints(place: Place, constraints: list[str]) -> tuple[bool, str | None]:
    """Check whether a place violates any user constraint.

    Returns:
        (True,  None)    → hard reject, drop the place entirely
        (False, warning) → soft warning, keep but surface the note
        (False, None)    → no issue, place is clean
    """
    type_str   = " ".join(place.types).lower()
    name_lower = place.name.lower()

    for c in constraints:

        # ── Vegetarian ────────────────────────────────────────────────────────
        if "veg" in c:
            if any(kw in type_str for kw in NON_VEG_KEYWORDS):
                return True, None                           # non-veg venue type
            if "meat" in name_lower or "barbecue" in name_lower or "kebab" in name_lower:
                return True, None                           # non-veg name keyword

        # ── Avoid crowds ──────────────────────────────────────────────────────
        if "avoid crowded" in c or "no crowd" in c or "not crowded" in c:
            if place.user_rating_count and place.user_rating_count > 30_000:
                return False, "Popular spot — may get crowded"      # very high footfall
            if any(t in CROWDED_TYPES for t in place.types):
                return False, "Tends to be a crowded venue"         # inherently busy category

        # ── Quiet ─────────────────────────────────────────────────────────────
        if "quiet" in c:
            if place.user_rating_count and place.user_rating_count > 20_000:
                return False, "Quite popular, may not feel as quiet"

    return False, None


def _score_place(place: Place, prefs: ParsedPreferences) -> tuple[float, str | None]:
    """Score a place 0–10 based on rating, popularity, budget fit, interests, and energy match.

    Returns:
        (score, trade_off_message | None)
    """
    score:      float       = 5.0   # neutral baseline
    trade_off:  str | None  = None

    # ── Star rating ───────────────────────────────────────────────────────────
    # 3.5 is the neutral midpoint; e.g. 4.5 → +1.5 | 3.0 → −0.75
    if place.rating is not None:
        score += (place.rating - 3.5) * 1.5

    # ── Review count (popularity signal) ─────────────────────────────────────
    if place.user_rating_count:
        if place.user_rating_count > 500:
            score += 0.5    # reasonably reviewed
        if place.user_rating_count > 5_000:
            score += 0.5    # stacks → +1.0 total

    # ── Budget fit + premium bias ─────────────────────────────────────────────
    per_stop = _per_stop_budget(prefs)          # total budget ÷ estimated stops

    if place.estimated_cost <= per_stop:
        score += 1.5                            # within budget
        # When budget is generous, reward higher price_level places — a high
        # budget signals the user wants quality, not just cheap options.
        if per_stop > 1500 and place.price_level is not None:
            score += place.price_level * 0.4   # price_level 3 → +1.2, level 4 → +1.6

    elif place.estimated_cost <= per_stop * 1.3:
        score -= 0.5                            # up to 30 % over — marginal, keep but warn
        trade_off = (
            f"Slightly over per-stop budget"
            f" (est. ~{int(place.estimated_cost)} vs ~{int(per_stop)})"
        )
    else:
        score -= 3.0                            # >30 % over — heavy penalty
        trade_off = (
            f"Significantly over per-stop budget"
            f" (est. ~{int(place.estimated_cost)} vs ~{int(per_stop)})"
        )

    # ── Interest match ────────────────────────────────────────────────────────
    # Each matching interest adds +0.5; multiple interests stack
    type_str   = " ".join(place.types).lower()
    name_lower = place.name.lower()
    for interest in prefs.interests:
        if interest in type_str or interest in name_lower:
            score += 0.5

    # ── Energy level fit ──────────────────────────────────────────────────────
    if prefs.energy_level == "low"  and any(t in CROWDED_TYPES for t in place.types):
        score -= 1.0    # low-energy user + high-stimulation venue = bad fit
    if prefs.energy_level == "high" and "park" in type_str:
        score -= 0.3    # mild penalty: parks are too passive for a high-energy day

    score = max(0.0, min(10.0, score))          # clamp to [0, 10]
    return score, trade_off


def filter_options(places: list[Place], prefs: ParsedPreferences) -> dict:
    approved:   list[Place] = []
    borderline: list[Place] = []
    low_scored: list[Place] = []   # scored but fell below borderline threshold
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
            # Keep low-scored places as a last resort instead of discarding them
            place.is_borderline = True
            place.trade_off = (place.trade_off or "") + (
                "; Best available option despite low score" if place.trade_off
                else "Best available option despite low score"
            )
            low_scored.append(place)

    approved.sort(key=lambda p: p.score, reverse=True)
    borderline.sort(key=lambda p: p.score, reverse=True)
    low_scored.sort(key=lambda p: p.score, reverse=True)

    # ── Fallback: if nothing passed the thresholds, surface the least-bad options ──
    if not approved and not borderline:
        borderline = low_scored[:MAX_BORDERLINE]
        low_scored = []

    return {
        "approved":           approved[:MAX_APPROVED],
        "borderline":         borderline[:MAX_BORDERLINE],
        "rejected_count":     rejected_count + len(low_scored),
        "candidates_exhausted": (len(approved) + len(borderline)) == 0,
    }
