import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import notifier


@patch("notifier.requests.post")
def test_push_error_posts_to_telegram(mock_post):
    config = {"telegram_bot_token": "tok", "telegram_chat_id": "123"}
    notifier.push_error(config, "AI job processing", "getaddrinfo failed")

    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert "tok" in args[0]
    assert kwargs["json"]["chat_id"] == "123"
    assert "AI job processing" in kwargs["json"]["text"]
    assert "getaddrinfo failed" in kwargs["json"]["text"]


@patch("notifier.requests.post")
def test_push_error_noop_without_telegram_config(mock_post):
    notifier.push_error({}, "Send cycle", "boom")
    mock_post.assert_not_called()


@patch("notifier.requests.post")
def test_push_error_does_not_raise_on_telegram_failure(mock_post):
    import requests
    mock_post.side_effect = requests.exceptions.ConnectionError("no network")

    config = {"telegram_bot_token": "tok", "telegram_chat_id": "123"}
    notifier.push_error(config, "Reply check", "boom")  # must not raise


@patch("notifier.requests.post")
def test_push_notifications_enables_html_parse_mode_for_email_sent(mock_post):
    config = {
        "telegram_bot_token": "tok", "telegram_chat_id": "123",
        "pending_notifications": [
            {"id": 1, "level": "info", "type": "email_sent", "message": "<b>Sent Mail</b>\nCompany: Acme"},
        ],
    }
    notifier.push_notifications(config, report_pushed_fn=lambda ids: None)

    kwargs = mock_post.call_args.kwargs
    assert kwargs["json"]["parse_mode"] == "HTML"


@patch("notifier.requests.post")
def test_push_notifications_leaves_parse_mode_off_for_other_types(mock_post):
    """Only email_sent is built with escaped HTML — every other notification
    type sends free-form, unescaped text, so parse_mode must stay unset for
    those or Telegram could reject a message over a stray "<" or "&"."""
    config = {
        "telegram_bot_token": "tok", "telegram_chat_id": "123",
        "pending_notifications": [
            {"id": 2, "level": "error", "type": "smtp_error", "message": "Send failed: <weird & broken>"},
        ],
    }
    notifier.push_notifications(config, report_pushed_fn=lambda ids: None)

    kwargs = mock_post.call_args.kwargs
    assert "parse_mode" not in kwargs["json"]
