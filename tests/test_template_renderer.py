import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from template_renderer import build_mime


def test_build_mime_sets_headers_and_body():
    item = {
        "subject": "Hi there",
        "to_email": "lead@example.com",
        "message_id": "<abc@outreach.local>",
        "in_reply_to": "<parent@outreach.local>",
        "references": "<parent@outreach.local>",
        "body": "Hello world",
    }
    msg = build_mime(item, "sender@example.com")

    assert msg["Subject"] == "Hi there"
    assert msg["From"] == "sender@example.com"
    assert msg["To"] == "lead@example.com"
    assert msg["Message-ID"] == "<abc@outreach.local>"
    assert msg["In-Reply-To"] == "<parent@outreach.local>"
    assert msg["References"] == "<parent@outreach.local>"
    assert msg.get_content().strip() == "Hello world"


def test_build_mime_omits_threading_headers_when_absent():
    item = {
        "subject": "Hi", "to_email": "lead@example.com", "message_id": "<x@outreach.local>",
        "in_reply_to": "", "references": "", "body": "Hello",
    }
    msg = build_mime(item, "sender@example.com")
    assert msg["In-Reply-To"] is None
    assert msg["References"] is None


def test_build_mime_stays_plain_text_only_even_if_body_html_present():
    """Plain text only, deliberately — no HTML alternative is ever attached,
    even if a caller still passes a body_html value (e.g. an old payload
    shape). See template_service.py render_template() for why."""
    item = {
        "subject": "Hi", "to_email": "lead@example.com", "message_id": "<x@outreach.local>",
        "body": "Hello world", "body_html": "<html><body><p>Hello world</p></body></html>",
    }
    msg = build_mime(item, "sender@example.com")

    assert not msg.is_multipart()
    assert msg.get_content().strip() == "Hello world"


def test_build_mime_stays_plain_text_only_when_no_html():
    item = {
        "subject": "Hi", "to_email": "lead@example.com", "message_id": "<x@outreach.local>", "body": "Hello",
    }
    msg = build_mime(item, "sender@example.com")
    assert not msg.is_multipart()
