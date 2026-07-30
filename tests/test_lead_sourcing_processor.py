import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import lead_sourcing_processor


@patch("lead_sourcing_processor.api_client.report_lead_sourcing_results")
@patch("lead_sourcing_processor.google_places_client.search_text")
@patch("lead_sourcing_processor.api_client.fetch_lead_sourcing_pending")
def test_process_lead_sourcing_happy_path(mock_fetch, mock_search, mock_report):
    mock_fetch.return_value = {
        "query": "plumber in Austin, TX, US", "niche": "plumber", "country": "US", "state": "TX",
        "page_token": None, "api_key": "sk-test",
    }
    mock_search.return_value = ([{"place_id": "p1", "business_name": "Acme"}], "next-tok", None, False)

    lead_sourcing_processor.process_lead_sourcing()

    mock_search.assert_called_once_with("plumber in Austin, TX, US", "sk-test", page_token=None)
    payload = mock_report.call_args[0][0]
    assert payload["query"] == "plumber in Austin, TX, US"
    assert payload["niche"] == "plumber"
    assert payload["country"] == "US"
    assert payload["state"] == "TX"
    assert payload["results"] == [{"place_id": "p1", "business_name": "Acme"}]
    assert payload["next_page_token"] == "next-tok"
    assert payload["error"] is None


@patch("lead_sourcing_processor.api_client.report_lead_sourcing_results")
@patch("lead_sourcing_processor.google_places_client.search_text")
@patch("lead_sourcing_processor.api_client.fetch_lead_sourcing_pending")
def test_process_lead_sourcing_noop_when_no_job(mock_fetch, mock_search, mock_report):
    mock_fetch.return_value = {}
    lead_sourcing_processor.process_lead_sourcing()
    mock_search.assert_not_called()
    mock_report.assert_not_called()


@patch("lead_sourcing_processor.api_client.report_lead_sourcing_results")
@patch("lead_sourcing_processor.google_places_client.search_text")
@patch("lead_sourcing_processor.api_client.fetch_lead_sourcing_pending")
def test_process_lead_sourcing_reports_error(mock_fetch, mock_search, mock_report):
    mock_fetch.return_value = {
        "query": "plumber in Austin, TX, US", "niche": "plumber", "country": "US", "state": "TX",
        "page_token": None, "api_key": "sk-bad",
    }
    mock_search.return_value = ([], None, "401: Unauthorized", True)

    lead_sourcing_processor.process_lead_sourcing()

    payload = mock_report.call_args[0][0]
    assert payload["error"] == "401: Unauthorized"
    assert payload["is_key_error"] is True
