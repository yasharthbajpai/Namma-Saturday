"""Tool 5 — Validate the itinerary against the user's budget.

Pure Python. Sums estimated costs. If over budget, trims the most expensive item
(unless that brings us under a 2-item minimum). Flags any trade-offs introduced.
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

    items = list(itinerary)
    total = sum(i.estimated_cost for i in items)
    extra_trade_offs: list[str] = []

    while total > prefs.budget and len(items) > 2:
        items.sort(key=lambda i: i.estimated_cost, reverse=True)
        dropped = items.pop(0)
        extra_trade_offs.append(
            f"Dropped '{dropped.place_name}' (~{int(dropped.estimated_cost)}) to stay within budget."
        )
        total = sum(i.estimated_cost for i in items)

    items.sort(key=lambda i: i.time_slot)

    budget_ok = total <= prefs.budget
    if not budget_ok:
        extra_trade_offs.append(
            f"Plan is ~{int(total - prefs.budget)} over your budget — kept the essentials anyway."
        )

    return {
        "itinerary": items,
        "total_cost": round(total, 2),
        "extra_trade_offs": extra_trade_offs,
        "budget_ok": budget_ok,
    }
