"""Tool 2 — Build search queries from preferences and fetch candidates from Google Places.

If the API fails, falls back to a small hardcoded set of well-known places so the
rest of the pipeline can continue.
"""

from models.domain import ParsedPreferences, Place
from services.google_places import search_places, GooglePlacesError


# Per-stop budget thresholds (total budget / estimated stops)
BUDGET_LOW      = 500    # under ₹500/stop  → budget-friendly queries
BUDGET_MEDIUM   = 1500   # ₹500–1500/stop   → default queries
BUDGET_HIGH     = 1500   # above ₹1500/stop → premium queries

# Three tiers of query templates: budget / default / premium
INTEREST_QUERIES: dict[str, tuple[str, str, str]] = {
    # interest: (budget_query, default_query, premium_query)
    "food":      ("{veg}budget restaurants in {city}",
                  "{veg}restaurants in {city}",
                  "{veg}fine dining restaurants in {city}"),
    "music":     ("live music bars in {city}",
                  "live music venues and pubs in {city}",
                  "best live music and jazz clubs in {city}"),
    "walks":     ("parks and free walking spots in {city}",
                  "parks, lakes and walking trails in {city}",
                  "scenic parks and nature walks in {city}"),
    "art":       ("free art galleries and museums in {city}",
                  "art galleries and museums in {city}",
                  "best art galleries and cultural centres in {city}"),
    "shopping":  ("budget markets and street shopping in {city}",
                  "shopping streets and markets in {city}",
                  "upscale malls and boutique shopping in {city}"),
    "coffee":    ("local cafes and coffee shops in {city}",
                  "specialty coffee shops and cafes in {city}",
                  "best specialty third wave coffee in {city}"),
    "books":     ("second hand bookstores in {city}",
                  "bookstores and reading cafes in {city}",
                  "best bookstores and literary cafes in {city}"),
    "movies":    ("cinemas in {city}",
                  "cinemas and indie theatres in {city}",
                  "premium cinemas and IMAX in {city}"),
    "nature":    ("gardens and free nature spots in {city}",
                  "gardens and nature spots in {city}",
                  "best botanical gardens and scenic nature in {city}"),
    "nightlife": ("bars and pubs in {city}",
                  "rooftop bars and nightlife in {city}",
                  "best rooftop bars and premium nightlife in {city}"),
}


def _per_stop_budget(prefs: ParsedPreferences) -> float:
    stops = max(2, int(prefs.hours_available // 1.5))
    return prefs.budget / stops


def _query_tier(prefs: ParsedPreferences) -> int:
    """Return 0=budget, 1=default, 2=premium based on per-stop budget."""
    per_stop = _per_stop_budget(prefs)
    if per_stop < BUDGET_LOW:
        return 0
    if per_stop < BUDGET_HIGH:
        return 1
    return 2


def _build_queries(prefs: ParsedPreferences) -> list[str]:
    veg_prefix = ""
    if any("veg" in c for c in prefs.constraints):
        veg_prefix = "vegetarian "

    tier = _query_tier(prefs)
    queries: list[str] = []

    for interest in prefs.interests:
        templates = INTEREST_QUERIES.get(interest)
        if templates:
            template = templates[tier]
        else:
            template = "{veg}" + interest + " spots in {city}"
        queries.append(template.format(veg=veg_prefix, city=prefs.city))

    if "food" not in prefs.interests:
        food_templates = INTEREST_QUERIES["food"]
        queries.append(food_templates[tier].format(veg=veg_prefix, city=prefs.city))

    return queries


def _estimate_cost(price_level: int | None, place_types: list[str]) -> float:
    """Map Google price_level (0-4) to a rough cost estimate in INR."""
    if price_level is None:
        if any(t in {"park", "tourist_attraction", "museum"} for t in place_types):
            return 0.0
        return 500.0
    cost_table = {0: 0.0, 1: 300.0, 2: 700.0, 3: 1800.0, 4: 4000.0}
    return cost_table.get(price_level, 700.0)


def _fallback_places(prefs: ParsedPreferences) -> list[Place]:
    """Hardcoded popular Bangalore-ish fallback so the pipeline still works."""
    city = prefs.city
    raw = [
        {"name": "Cubbon Park", "types": ["park"], "rating": 4.6, "user_rating_count": 50000, "price_level": 0, "address": f"Central {city}"},
        {"name": "MTR (Mavalli Tiffin Room)", "types": ["restaurant", "vegetarian"], "rating": 4.4, "user_rating_count": 30000, "price_level": 1, "address": f"Lalbagh Rd, {city}"},
        {"name": "Lalbagh Botanical Garden", "types": ["park", "tourist_attraction"], "rating": 4.6, "user_rating_count": 40000, "price_level": 0, "address": f"Mavalli, {city}"},
        {"name": "Third Wave Coffee", "types": ["cafe"], "rating": 4.3, "user_rating_count": 5000, "price_level": 2, "address": f"Indiranagar, {city}"},
        {"name": "Indigo Live Music Bar", "types": ["bar", "live_music_venue"], "rating": 4.3, "user_rating_count": 8000, "price_level": 3, "address": f"Indiranagar, {city}"},
        {"name": "Blossom Book House", "types": ["book_store"], "rating": 4.6, "user_rating_count": 12000, "price_level": 1, "address": f"Church Street, {city}"},
        {"name": "Brahmin's Coffee Bar", "types": ["restaurant", "vegetarian"], "rating": 4.5, "user_rating_count": 8000, "price_level": 1, "address": f"Shankarpuram, {city}"},
        {"name": "Sankey Tank", "types": ["park"], "rating": 4.5, "user_rating_count": 15000, "price_level": 0, "address": f"Sadashivnagar, {city}"},
    ]
    return [
        Place(
            name=r["name"],
            types=r["types"],
            rating=r["rating"],
            user_rating_count=r["user_rating_count"],
            price_level=r["price_level"],
            address=r["address"],
            estimated_cost=_estimate_cost(r["price_level"], r["types"]),
            source="fallback",
        )
        for r in raw
    ]


async def get_options(prefs: ParsedPreferences) -> tuple[list[Place], bool]:
    """Return (candidates, used_fallback)."""
    queries = _build_queries(prefs)

    try:
        raw_places = await search_places(queries)
    except GooglePlacesError:
        return _fallback_places(prefs), True

    if not raw_places:
        return _fallback_places(prefs), True

    candidates: list[Place] = []
    for raw in raw_places:
        candidates.append(
            Place(
                name=raw["name"],
                types=raw.get("types", []),
                rating=raw.get("rating"),
                user_rating_count=raw.get("user_rating_count"),
                price_level=raw.get("price_level"),
                address=raw.get("address", ""),
                place_id=raw.get("place_id", ""),
                maps_url=raw.get("maps_url", ""),
                estimated_cost=_estimate_cost(raw.get("price_level"), raw.get("types", [])),
                source="google_places",
            )
        )

    return candidates, False
