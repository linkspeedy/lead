"""Shared inbound-message parsing for reply_checker.py (IMAP) and
gmail_client.py (Gmail API) — both end up with a standard
email.message.Message and need to build the same payload shape for
api_client.report_reply_detected, so the parsing lives in one place rather
than being duplicated (or forcing a circular import between the two)."""

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


def build_payload(message):
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
