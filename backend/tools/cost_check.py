"""Tool 5 — Validate the itinerary's total cost against the user's budget.

Trimming is NOT done here. Budget enforcement happens in Tool 3 (filter_options)
before candidates reach Claude. Claude is responsible for respecting the budget
when building the itinerary in Tool 4.

This tool only sums the costs and flags if Claude went over — adding a trade-off
note so the user sees it, but leaving the itinerary intact.
"""

from models.domain import ParsedPreferences, ItineraryItem


def cost_check(itinerary: list[ItineraryItem], prefs: ParsedPreferences) -> dict:
    if not itinerary:
        return {
            "itinerary": [],
            "total_cost": 0.0,
            "extra_trade_offs": [],
            "budget_ok": True,
        }

    total = round(sum(i.estimated_cost for i in itinerary), 2)
    overage = round(total - prefs.budget, 2)
    budget_ok = overage <= 0

    extra_trade_offs: list[str] = []
    if not budget_ok:
        extra_trade_offs.append(
            f"Plan is ~₹{int(overage)} over your budget — "
            "consider dropping one stop or adjusting your budget."
        )

    return {
        "itinerary": itinerary,
        "total_cost": total,
        "extra_trade_offs": extra_trade_offs,
        "budget_ok": budget_ok,
    }
