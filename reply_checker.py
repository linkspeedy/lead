"""IMAP polling. Zero relevance filtering by design — every new message is
forwarded to Django (via the report_fn callback, normally
api_client.report_reply_detected), which alone decides whether it matches a
known lead/campaign (see django_app/campaigns/services/reply_service.py).
The worker never decides which replies matter."""

import email
import imaplib
from email.header import decode_header
from email.utils import parseaddr, parsedate_to_datetime


def _decode(value):
    if not value:
        return ""
    parts = decode_header(value)
    return "".join(
        (part.decode(enc or "utf-8", errors="ignore") if isinstance(part, bytes) else part)
        for part, enc in parts
    )


def _extract_snippet(message):
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_type() == "text/plain" and not part.get("Content-Disposition"):
                charset = part.get_content_charset() or "utf-8"
                payload = part.get_payload(decode=True)
                return payload.decode(charset, errors="ignore") if payload else ""
        return ""
    charset = message.get_content_charset() or "utf-8"
    payload = message.get_payload(decode=True)
    return payload.decode(charset, errors="ignore") if payload else ""


def _build_payload(message):
    payload = {
        "message_id": message.get("Message-ID", ""),
        "in_reply_to": message.get("In-Reply-To", ""),
        "references": message.get("References", ""),
        "from_email": parseaddr(message.get("From", ""))[1],
        "subject": _decode(message.get("Subject", "")),
        "body_snippet": _extract_snippet(message)[:1000],
        "thread_id": message.get("Message-ID", ""),
    }
    date_header = message.get("Date")
    if date_header:
        try:
            payload["received_at"] = parsedate_to_datetime(date_header).isoformat()
        except (TypeError, ValueError):
            pass
    return payload


def check_replies(imap_config, report_fn):
    """Connects, finds unseen messages, forwards each to Django, and marks
    it \\Seen only after a successful report — a crash mid-cycle re-sees the
    same message next poll instead of silently losing it. BODY.PEEK[] is
    used for the fetch itself so merely reading a message never marks it
    seen before Django has actually processed it."""
    if not imap_config:
        return

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
            payload = _build_payload(message)

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
