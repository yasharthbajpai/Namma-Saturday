"""Google Places Text Search (New) wrapper.

Uses the v1 Places API with a field mask to only fetch the data we need.
Returns a list of normalised place dicts; raises GooglePlacesError on failure.
"""

import asyncio
import httpx
from core.config import settings


PLACES_TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
FIELD_MASK = (
    "places.id,"
    "places.displayName,"
    "places.rating,"
    "places.userRatingCount,"
    "places.priceLevel,"
    "places.formattedAddress,"
    "places.types,"
    "places.currentOpeningHours.openNow"
)

PRICE_LEVEL_MAP = {
    "PRICE_LEVEL_FREE": 0,
    "PRICE_LEVEL_INEXPENSIVE": 1,
    "PRICE_LEVEL_MODERATE": 2,
    "PRICE_LEVEL_EXPENSIVE": 3,
    "PRICE_LEVEL_VERY_EXPENSIVE": 4,
}


class GooglePlacesError(Exception):
    pass


def _maps_url(place_id: str, name: str = "") -> str:
    if not place_id:
        return ""
    from urllib.parse import quote_plus
    q = quote_plus(name) if name else quote_plus(f"place_id:{place_id}")
    return f"https://www.google.com/maps/search/?api=1&query={q}&query_place_id={place_id}"


def _normalise_place(raw: dict) -> dict:
    price_level_str = raw.get("priceLevel")
    price_level = PRICE_LEVEL_MAP.get(price_level_str) if price_level_str else None
    display_name = raw.get("displayName", {})
    name = display_name.get("text", "") if isinstance(display_name, dict) else str(display_name)
    open_now = None
    opening = raw.get("currentOpeningHours")
    if isinstance(opening, dict):
        open_now = opening.get("openNow")
    place_id = raw.get("id", "")

    return {
        "name": name,
        "types": raw.get("types", []),
        "rating": raw.get("rating"),
        "user_rating_count": raw.get("userRatingCount"),
        "price_level": price_level,
        "address": raw.get("formattedAddress", ""),
        "place_id": place_id,
        "maps_url": _maps_url(place_id, name),
        "open_now": open_now,
    }


async def _search_one(client: httpx.AsyncClient, query: str) -> list[dict]:
    if not settings.GOOGLE_PLACES_API_KEY:
        raise GooglePlacesError("GOOGLE_PLACES_API_KEY is not configured")

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": settings.GOOGLE_PLACES_API_KEY,
        "X-Goog-FieldMask": FIELD_MASK,
    }
    body = {"textQuery": query, "maxResultCount": 10}

    try:
        resp = await client.post(PLACES_TEXT_SEARCH_URL, headers=headers, json=body, timeout=15.0)
    except httpx.HTTPError as exc:
        raise GooglePlacesError(f"Network error calling Google Places: {exc}") from exc

    if resp.status_code != 200:
        raise GooglePlacesError(f"Google Places returned {resp.status_code}: {resp.text[:200]}")

    data = resp.json()
    raw_places = data.get("places", [])
    return [_normalise_place(p) for p in raw_places]


async def search_places(queries: list[str]) -> list[dict]:
    """Run multiple text searches concurrently and return the merged, de-duplicated list."""
    if not queries:
        return []

    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(
            *[_search_one(client, q) for q in queries], return_exceptions=True
        )

    merged: list[dict] = []
    seen_names: set[str] = set()
    errors: list[str] = []

    for r in results:
        if isinstance(r, Exception):
            errors.append(str(r))
            continue
        for place in r:
            key = place["name"].lower().strip()
            if key and key not in seen_names:
                seen_names.add(key)
                merged.append(place)

    if not merged and errors:
        raise GooglePlacesError(f"All Places searches failed: {errors[0]}")

    return merged
