import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import campaign_processor


@patch("campaign_processor.api_client.report_email_sent")
@patch("campaign_processor.email_sender.send")
@patch("campaign_processor.api_client.fetch_sendable")
def test_process_sendable_reports_success(mock_fetch, mock_send, mock_report):
    mock_fetch.return_value = [{
        "tracking_id": 1, "sequence_step_id": 2, "to_email": "lead@test.com",
        "subject": "Hi", "body": "Hello", "body_html": "<html><body>Hello</body></html>",
        "message_id": "<a@x>", "in_reply_to": "", "thread_id": "<a@x>",
        "smtp_config": {"host": "smtp.test", "port": 587, "from_email": "s@test.com"},
    }]
    mock_send.return_value = (True, "250 OK", None, False)

    campaign_processor.process_sendable()

    mock_report.assert_called_once()
    payload = mock_report.call_args[0][0]
    assert payload["tracking_id"] == 1
    assert payload["status"] == "sent"
    assert payload["smtp_response"] == "250 OK"
    assert payload["body_html"] == "<html><body>Hello</body></html>"


@patch("campaign_processor.api_client.report_email_sent")
@patch("campaign_processor.email_sender.send")
@patch("campaign_processor.api_client.fetch_sendable")
def test_process_sendable_sends_a_batch_with_no_delay_between_items(mock_fetch, mock_send, mock_report):
    """Regression test: a batch must fire back-to-back — no artificial
    delay between individual sends (the old 20-90s human-like pacing was
    explicitly removed per the user's request for an immediate Send Now)."""
    mock_fetch.return_value = [
        {
            "tracking_id": i, "sequence_step_id": 2, "to_email": f"lead{i}@test.com",
            "subject": "Hi", "body": "Hello", "message_id": f"<{i}@x>", "in_reply_to": "", "thread_id": f"<{i}@x>",
            "smtp_config": {"host": "smtp.test", "port": 587, "from_email": "s@test.com"},
        }
        for i in range(3)
    ]
    mock_send.return_value = (True, "250 OK", None, False)

    campaign_processor.process_sendable()

    assert mock_report.call_count == 3
    assert not hasattr(campaign_processor, "time")  # no time.sleep import left to call


@patch("campaign_processor.api_client.report_email_sent")
@patch("campaign_processor.email_sender.send")
@patch("campaign_processor.api_client.fetch_sendable")
def test_process_sendable_reports_connection_error(mock_fetch, mock_send, mock_report):
    """A connection-level failure (timeout, DNS, dropped connection) is
    reported as "connection_error", not "failed" — Django retries these
    instead of permanently bouncing the lead (see send_report_service.py)."""
    mock_fetch.return_value = [{
        "tracking_id": 1, "sequence_step_id": 2, "to_email": "lead@test.com",
        "subject": "Hi", "body": "Hello", "message_id": "<a@x>", "in_reply_to": "", "thread_id": "<a@x>",
        "smtp_config": {"host": "smtp.test", "port": 587, "from_email": "s@test.com"},
    }]
    mock_send.return_value = (False, "", "Connection timed out", True)

    campaign_processor.process_sendable()

    payload = mock_report.call_args[0][0]
    assert payload["status"] == "connection_error"
    assert payload["smtp_response"] == "Connection timed out"


@patch("campaign_processor.api_client.report_email_sent")
@patch("campaign_processor.email_sender.send")
@patch("campaign_processor.api_client.fetch_sendable")
def test_process_sendable_reports_real_bounce_as_failed(mock_fetch, mock_send, mock_report):
    mock_fetch.return_value = [{
        "tracking_id": 1, "sequence_step_id": 2, "to_email": "lead@test.com",
        "subject": "Hi", "body": "Hello", "message_id": "<a@x>", "in_reply_to": "", "thread_id": "<a@x>",
        "smtp_config": {"host": "smtp.test", "port": 587, "from_email": "s@test.com"},
    }]
    mock_send.return_value = (False, "", "Recipients refused: {...}", False)

    campaign_processor.process_sendable()

    payload = mock_report.call_args[0][0]
    assert payload["status"] == "failed"


@patch("campaign_processor.api_client.report_ai_completed")
@patch("campaign_processor.ai_client.generate_text")
@patch("campaign_processor.api_client.fetch_ai_pending")
def test_process_ai_jobs_success(mock_fetch, mock_generate, mock_report):
    mock_fetch.return_value = [{"tracking_id": 5, "prompt": "write something"}]
    mock_generate.return_value = ("Great opening line.", None, False, False)

    campaign_processor.process_ai_jobs({"ai_config": {"api_key": "sk", "model_name": "m"}})

    mock_report.assert_called_once_with({"tracking_id": 5, "text": "Great opening line."})


@patch("campaign_processor.api_client.report_ai_completed")
@patch("campaign_processor.ai_client.generate_text")
@patch("campaign_processor.api_client.fetch_ai_pending")
def test_process_ai_jobs_reports_connection_error(mock_fetch, mock_generate, mock_report):
    mock_fetch.return_value = [{"tracking_id": 5, "prompt": "write something"}]
    mock_generate.return_value = (None, "getaddrinfo failed", False, True)

    campaign_processor.process_ai_jobs({"ai_config": {"api_key": "sk", "model_name": "m"}})

    mock_report.assert_called_once_with({
        "tracking_id": 5, "error": "getaddrinfo failed",
        "is_key_error": False, "is_connection_error": True,
    })


@patch("campaign_processor.api_client.fetch_ai_pending")
def test_process_ai_jobs_noop_without_config(mock_fetch):
    campaign_processor.process_ai_jobs({"ai_config": None})
    mock_fetch.assert_not_called()
