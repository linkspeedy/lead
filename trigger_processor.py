"""Executes WorkerTrigger rows Django can't act on directly (see
django_app/core/models.py WorkerTrigger and django_app/core/viewsets.py
SendTestEmailView) — same fetch/execute/report pattern as every other
worker module. Only send_test_email is implemented; any other trigger_type
is reported back as an error rather than left queued forever."""

from email.utils import make_msgid

import api_client
import email_sender
from template_renderer import build_mime


def _send_test_email(trigger, smtp_config):
    to_email = trigger.get("payload", {}).get("to_email")
    if not smtp_config:
        return False, "No active SMTP configuration."
    if not to_email:
        return False, "No recipient address on the trigger."

    from_email = smtp_config["from_email"]
    msgid_domain = from_email.split("@")[-1] if "@" in from_email else "outreach.local"
    item = {
        "subject": "ROJEX Outreach — Test Email",
        "to_email": to_email,
        "message_id": make_msgid(domain=msgid_domain),
        "body": (
            "This is a test email from your ROJEX Outreach setup.\n\n"
            "If you're reading this, your SMTP configuration is working correctly."
        ),
    }
    mime_message = build_mime(item, smtp_config["from_email"])
    success, response, error, _is_connection_error = email_sender.send(mime_message, smtp_config)
    return success, response if success else error


def process_pending_triggers(config):
    triggers = config.get("pending_triggers") or []
    if not triggers:
        return

    smtp_config = config.get("smtp_config")
    for trigger in triggers:
        if trigger["trigger_type"] == "send_test_email":
            success, message = _send_test_email(trigger, smtp_config)
            status = "done" if success else "error"
        else:
            success, message, status = False, f"Unhandled trigger type: {trigger['trigger_type']}", "error"

        try:
            api_client.report_trigger_complete(trigger["id"], status, {"message": message})
        except Exception as e:
            print(f"Failed to report trigger {trigger['id']} completion: {e}")
