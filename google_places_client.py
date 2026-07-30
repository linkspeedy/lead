"""Proxies one Google Places API (New) Text Search call. Django decides
WHAT to search for (the query string, built from country/state/niche
criteria in leads/services/lead_sourcing_service.py) and WHETHER a search
is due at all — this module only executes the HTTP call, because Django
(on PythonAnywhere's free tier) can't reach Google directly. It never
decides business logic.

Field masking below is itself a cost control: the New Places API bills
per-request based on which fields are requested, so only the fields the
app actually stores are asked for."""

import requests

SEARCH_TEXT_URL = "https://places.googleapis.com/v1/places:searchText"
FIELD_MASK = (
    "places.id,places.displayName,places.formattedAddress,"
    "places.internationalPhoneNumber,places.websiteUri,"
    "places.rating,places.userRatingCount,nextPageToken"
)
# Confirmed against a real (deliberately invalid) key: Google's Places API
# (New) reports an invalid/unauthorized key as HTTP 400 with one of these
# reason codes in the body, NOT a 401/403 like most APIs — checking the
# plain status code alone (as REST APIs conventionally do) misses this
# entirely and would let a run silently retry a dead key forever.
KEY_ERROR_REASONS = ("API_KEY_INVALID", "PERMISSION_DENIED", "UNAUTHENTICATED")


def _is_key_error(status_code, body_json):
    if status_code in (401, 403):
        return True
    reason = ((body_json or {}).get("error") or {}).get("status", "")
    details = ((body_json or {}).get("error") or {}).get("details") or []
    detail_reasons = [d.get("reason", "") for d in details if isinstance(d, dict)]
    return reason in KEY_ERROR_REASONS or any(r in KEY_ERROR_REASONS for r in detail_reasons)


def _normalize_place(place):
    return {
        "place_id": place.get("id", ""),
        "business_name": (place.get("displayName") or {}).get("text", ""),
        "formatted_address": place.get("formattedAddress", ""),
        "phone": place.get("internationalPhoneNumber", ""),
        "website": place.get("websiteUri", ""),
        "rating": place.get("rating"),
        "review_count": place.get("userRatingCount"),
    }


def search_text(query, api_key, page_token=None):
    """Returns (results, next_page_token, error, is_key_error). `results`
    is a list of normalized place dicts (see _normalize_place) ready to
    send back to Django as-is — the worker never needs to know Google's
    raw response shape beyond this one parsing step."""
    body = {"pageToken": page_token} if page_token else {"textQuery": query}
    if page_token:
        body["textQuery"] = query  # required on every page, not just the first

    try:
        resp = requests.post(
            SEARCH_TEXT_URL,
            headers={
                "Content-Type": "application/json",
                "X-Goog-Api-Key": api_key,
                "X-Goog-FieldMask": FIELD_MASK,
            },
            json=body,
            timeout=30,
        )
    except requests.RequestException as e:
        return [], None, str(e), False

    if not resp.ok:
        try:
            body_json = resp.json()
        except ValueError:
            body_json = None
        is_key_error = _is_key_error(resp.status_code, body_json)
        return [], None, f"{resp.status_code}: {resp.text[:300]}", is_key_error

    try:
        data = resp.json()
    except ValueError as e:
        return [], None, f"Unexpected Google Places response: {e}", False

    places = [_normalize_place(p) for p in data.get("places", [])]
    next_page_token = data.get("nextPageToken")
    return places, next_page_token, None, False
