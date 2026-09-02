"""Orchestrates one send-cycle and one AI-personalization cycle. Every
decision (who's due, what to say, whether AI is needed) has already been
made by Django — this module just executes fetch -> do the mechanical work
-> report back. A batch is sent back-to-back with no artificial delay
between items — the daily cap in eligibility_service.py is what bounds
volume, not pacing within a single poll."""

import ai_client
import api_client
import email_sender
from template_renderer import build_mime


def process_ai_jobs(config):
    ai_config = config.get("ai_config")
    if not ai_config:
        return

    jobs = api_client.fetch_ai_pending()
    for job in jobs:
        text, error, is_key_error, is_connection_error = ai_client.generate_text(
            job["messages"], ai_config["api_key"], ai_config["model_name"], ai_config.get("provider", "openrouter")
        )
        if error:
            print(f"AI job failed for tracking {job['tracking_id']}: {error}")
            api_client.report_ai_completed({
                "tracking_id": job["tracking_id"], "error": error,
                "is_key_error": is_key_error, "is_connection_error": is_connection_error,
            })
        else:
            api_client.report_ai_completed({"tracking_id": job["tracking_id"], "text": text})


def process_sendable():
    items = api_client.fetch_sendable()
    for item in items:
        smtp_config = item["smtp_config"]
        mime_message = build_mime(item, smtp_config["from_email"])
        success, response, error, is_connection_error = email_sender.send(mime_message, smtp_config)

        if success:
            status = "sent"
        elif is_connection_error:
            status = "connection_error"
        else:
            status = "failed"

        api_client.report_email_sent({
            "tracking_id": item["tracking_id"],
            "sequence_step_id": item["sequence_step_id"],
            "smtp_config_id": item.get("smtp_config_id"),
            "message_id": item["message_id"],
            "subject": item["subject"],
            "body": item["body"],
            "body_html": item.get("body_html", ""),
            "recipient_email": item["to_email"],
            "in_reply_to": item.get("in_reply_to", ""),
            "thread_id": item.get("thread_id", ""),
            "smtp_response": response if success else (error or ""),
            "status": status,
        })

        if success:
            print(f"[SENT] {item['to_email']}")
        else:
            print(f"[FAILED] {item['to_email']}: {error}")
