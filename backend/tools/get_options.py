"""Tool 2 — Build search queries from preferences and fetch candidates from Google Places.

If the API fails, falls back to a small hardcoded set of well-known places so the
rest of the pipeline can continue.
"""

from models.domain import ParsedPreferences, Place
from services.google_places import search_places, GooglePlacesError


INTEREST_QUERY_TEMPLATES = {
    "food": "{veg}restaurants in {city}",
    "music": "live music venues and pubs with music in {city}",
    "walks": "parks, lakes and walking trails in {city}",
    "art": "art galleries and museums in {city}",
    "shopping": "shopping streets and markets in {city}",
    "coffee": "specialty coffee shops and cafes in {city}",
    "books": "bookstores and reading cafes in {city}",
    "movies": "cinemas and indie theatres in {city}",
    "nature": "gardens and nature spots in {city}",
    "nightlife": "rooftop bars and nightlife in {city}",
}


def _build_queries(prefs: ParsedPreferences) -> list[str]:
    veg_prefix = ""
    if any("veg" in c for c in prefs.constraints):
        veg_prefix = "vegetarian "

    queries: list[str] = []
    for interest in prefs.interests:
        template = INTEREST_QUERY_TEMPLATES.get(interest)
        if not template:
            template = "{veg}" + interest + " spots in {city}"
        queries.append(template.format(veg=veg_prefix, city=prefs.city))

    if "food" not in prefs.interests:
        queries.append(f"{veg_prefix}restaurants in {prefs.city}")

    return queries[:4]


def _estimate_cost(price_level: int | None, place_types: list[str]) -> float:
    """Map Google price_level (0-4) to a rough cost estimate in INR."""
    if price_level is None:
        if any(t in {"park", "tourist_attraction", "museum"} for t in place_types):
            return 0.0
        return 400.0
    cost_table = {0: 0.0, 1: 250.0, 2: 600.0, 3: 1200.0, 4: 2500.0}
    return cost_table.get(price_level, 600.0)


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
                estimated_cost=_estimate_cost(raw.get("price_level"), raw.get("types", [])),
                source="google_places",
            )
        )

    return candidates, False
