import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import google_places_client


def _mock_response(status_code=200, ok=True, json_data=None, text=""):
    return MagicMock(status_code=status_code, ok=ok, json=lambda: json_data or {}, text=text)


@patch("google_places_client.requests.post")
def test_search_text_success_normalizes_places(mock_post):
    mock_post.return_value = _mock_response(json_data={
        "places": [{
            "id": "place123",
            "displayName": {"text": "Acme Plumbing"},
            "formattedAddress": "123 Main St, Austin, TX",
            "internationalPhoneNumber": "+1 512-555-0100",
            "websiteUri": "https://acmeplumbing.test",
            "rating": 4.5,
            "userRatingCount": 87,
        }],
        "nextPageToken": "abc123",
    })

    results, next_page_token, error, is_key_error = google_places_client.search_text("plumber in Austin, TX", "sk-test")

    assert error is None
    assert is_key_error is False
    assert next_page_token == "abc123"
    assert len(results) == 1
    assert results[0] == {
        "place_id": "place123",
        "business_name": "Acme Plumbing",
        "formatted_address": "123 Main St, Austin, TX",
        "phone": "+1 512-555-0100",
        "website": "https://acmeplumbing.test",
        "rating": 4.5,
        "review_count": 87,
    }


@patch("google_places_client.requests.post")
def test_search_text_key_error_401(mock_post):
    mock_post.return_value = _mock_response(status_code=401, ok=False, text="Unauthorized")
    results, next_page_token, error, is_key_error = google_places_client.search_text("plumber", "sk-bad")
    assert results == []
    assert is_key_error is True
    assert "401" in error


@patch("google_places_client.requests.post")
def test_search_text_key_error_400_invalid_key(mock_post):
    """Confirmed against a real invalid key: the New Places API reports
    this as HTTP 400 with reason API_KEY_INVALID, not 401/403 — status
    code alone is not enough to detect this."""
    body = {
        "error": {
            "code": 400, "message": "API key not valid. Please pass a valid API key.",
            "status": "INVALID_ARGUMENT",
            "details": [{"reason": "API_KEY_INVALID", "domain": "googleapis.com"}],
        }
    }
    mock_post.return_value = _mock_response(status_code=400, ok=False, json_data=body, text=str(body))
    results, next_page_token, error, is_key_error = google_places_client.search_text("plumber", "sk-bad")
    assert results == []
    assert is_key_error is True


@patch("google_places_client.requests.post")
def test_search_text_other_error(mock_post):
    mock_post.return_value = _mock_response(status_code=500, ok=False, text="Server error")
    results, next_page_token, error, is_key_error = google_places_client.search_text("plumber", "sk-test")
    assert results == []
    assert is_key_error is False
    assert "500" in error


@patch("google_places_client.requests.post")
def test_search_text_sends_page_token(mock_post):
    mock_post.return_value = _mock_response(json_data={"places": []})
    google_places_client.search_text("plumber in Austin", "sk-test", page_token="tok123")
    sent_body = mock_post.call_args.kwargs["json"]
    assert sent_body["pageToken"] == "tok123"
    assert sent_body["textQuery"] == "plumber in Austin"


@patch("google_places_client.requests.post")
def test_search_text_field_mask_header_sent(mock_post):
    mock_post.return_value = _mock_response(json_data={"places": []})
    google_places_client.search_text("plumber", "sk-test")
    headers = mock_post.call_args.kwargs["headers"]
    assert headers["X-Goog-Api-Key"] == "sk-test"
    assert "places.id" in headers["X-Goog-FieldMask"]
