"""MIME assembly ONLY — never touches {{variables}}. Django's
campaigns/services/template_service.py already renders the final subject
and plain-text body before the worker ever sees them (see
eligibility_service.py's /api/worker/sendable/ response); personalization
is business logic, so it stays server-side. This module's only job is
turning that already-finished text into a properly-headered
email.message.EmailMessage for smtplib.

Plain text only, deliberately — no HTML alternative. A styled HTML email
reads as "marketing/bulk" from an unknown sender and undercuts the "real
person reaching out" tone, and plain text performs better for cold outreach
specifically. See campaigns/services/template_service.py render_template()."""

from email.message import EmailMessage


def build_mime(item, from_email):
    msg = EmailMessage()
    msg["Subject"] = item["subject"]
    msg["From"] = from_email
    msg["To"] = item["to_email"]
    msg["Message-ID"] = item["message_id"]
    if item.get("in_reply_to"):
        msg["In-Reply-To"] = item["in_reply_to"]
    if item.get("references"):
        msg["References"] = item["references"]

    msg.set_content(item["body"])
    return msg
