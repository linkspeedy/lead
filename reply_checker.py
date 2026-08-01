"""IMAP polling. Zero relevance filtering by design — every new message is
forwarded to Django (via the report_fn callback, normally
api_client.report_reply_detected), which alone decides whether it matches a
known lead/campaign (see django_app/campaigns/services/reply_service.py).
The worker never decides which replies matter."""

import email
import imaplib

import gmail_client
from email_parsing import build_payload


def check_replies(imap_config, report_fn):
    """Connects, finds unseen messages, forwards each to Django, and marks
    it \\Seen only after a successful report — a crash mid-cycle re-sees the
    same message next poll instead of silently losing it. BODY.PEEK[] is
    used for the fetch itself so merely reading a message never marks it
    seen before Django has actually processed it."""
    if not imap_config:
        return

    if imap_config.get("oauth_refresh_token"):
        return gmail_client.check_replies(imap_config, report_fn)

    conn_cls = imaplib.IMAP4_SSL if imap_config.get("use_ssl", True) else imaplib.IMAP4
    conn = conn_cls(imap_config["host"], imap_config["port"])

    try:
        conn.login(imap_config["username"], imap_config["password"])
        conn.select(imap_config.get("folder", "INBOX"))

        status, data = conn.search(None, "UNSEEN")
        if status != "OK" or not data or not data[0]:
            return

        for msg_num in data[0].split():
            status, msg_data = conn.fetch(msg_num, "(BODY.PEEK[])")
            if status != "OK" or not msg_data or not msg_data[0]:
                continue

            message = email.message_from_bytes(msg_data[0][1])
            payload = build_payload(message)

            try:
                report_fn(payload)
                conn.store(msg_num, "+FLAGS", "\\Seen")
            except Exception as e:
                print(f"Failed to report reply {payload.get('message_id')}: {e}")
    finally:
        try:
            conn.close()
        except Exception:
            pass
        try:
            conn.logout()
        except Exception:
            pass
