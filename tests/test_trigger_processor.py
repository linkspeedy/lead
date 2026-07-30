import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import trigger_processor

SMTP_CONFIG = {
    "host": "smtp.test", "port": 587, "username": "u", "password": "p",
    "use_tls": True, "use_ssl": False, "from_email": "sender@test.com",
}


@patch("trigger_processor.api_client.report_trigger_complete")
@patch("trigger_processor.email_sender.send")
def test_send_test_email_success(mock_send, mock_report):
    mock_send.return_value = (True, "250 Accepted", None, False)
    config = {
        "smtp_config": SMTP_CONFIG,
        "pending_triggers": [{"id": 1, "trigger_type": "send_test_email", "payload": {"to_email": "you@test.com"}}],
    }

    trigger_processor.process_pending_triggers(config)

    mock_send.assert_called_once()
    mock_report.assert_called_once_with(1, "done", {"message": "250 Accepted"})


@patch("trigger_processor.api_client.report_trigger_complete")
@patch("trigger_processor.email_sender.send")
def test_send_test_email_failure_reports_error(mock_send, mock_report):
    mock_send.return_value = (False, "", "550 Refused", True)
    config = {
        "smtp_config": SMTP_CONFIG,
        "pending_triggers": [{"id": 2, "trigger_type": "send_test_email", "payload": {"to_email": "you@test.com"}}],
    }

    trigger_processor.process_pending_triggers(config)

    mock_report.assert_called_once_with(2, "error", {"message": "550 Refused"})


@patch("trigger_processor.api_client.report_trigger_complete")
@patch("trigger_processor.email_sender.send")
def test_no_smtp_config_reports_error_without_sending(mock_send, mock_report):
    config = {
        "smtp_config": None,
        "pending_triggers": [{"id": 3, "trigger_type": "send_test_email", "payload": {"to_email": "you@test.com"}}],
    }

    trigger_processor.process_pending_triggers(config)

    mock_send.assert_not_called()
    mock_report.assert_called_once_with(3, "error", {"message": "No active SMTP configuration."})


@patch("trigger_processor.api_client.report_trigger_complete")
@patch("trigger_processor.email_sender.send")
def test_unhandled_trigger_type_reports_error(mock_send, mock_report):
    config = {
        "smtp_config": SMTP_CONFIG,
        "pending_triggers": [{"id": 4, "trigger_type": "process_campaign", "payload": {}}],
    }

    trigger_processor.process_pending_triggers(config)

    mock_send.assert_not_called()
    mock_report.assert_called_once_with(4, "error", {"message": "Unhandled trigger type: process_campaign"})


@patch("trigger_processor.api_client.report_trigger_complete")
@patch("trigger_processor.email_sender.send")
def test_noop_when_no_pending_triggers(mock_send, mock_report):
    trigger_processor.process_pending_triggers({"smtp_config": SMTP_CONFIG, "pending_triggers": []})
    mock_send.assert_not_called()
    mock_report.assert_not_called()
