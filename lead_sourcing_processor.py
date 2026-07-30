"""Orchestrates one lead-sourcing step per poll: ask Django if there's an
active search job, execute the one Google Places call it specifies, report
results back. Django owns all state (which query, which page, whether the
monthly cap is hit) — this module has no logic of its own beyond wiring
the two calls together."""

import api_client
import google_places_client


def process_lead_sourcing():
    job = api_client.fetch_lead_sourcing_pending()
    if not job:
        return

    results, next_page_token, error, is_key_error = google_places_client.search_text(
        job["query"], job["api_key"], page_token=job.get("page_token"),
    )

    if error:
        print(f"[LEAD SOURCING] {job['query']}: {error}")

    api_client.report_lead_sourcing_results({
        "query": job["query"],
        "niche": job.get("niche", ""),
        "country": job.get("country", ""),
        "state": job.get("state", ""),
        "results": results,
        "next_page_token": next_page_token,
        "error": error,
        "is_key_error": is_key_error,
    })
