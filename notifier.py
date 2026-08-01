"""Relays Django-created Notification rows to Telegram. Independent of
SMTP/email on purpose — an alert like "your SMTP config is broken" must not
depend on the very channel it's reporting as broken. Best-effort: a
Telegram outage must never interrupt sending or AI processing."""

import requests

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"

LEVEL_EMOJI = {"info": "ℹ️", "warning": "⚠️", "error": "❌"}

# Notification types that read as part of the actual email conversation
# (the sent message, or a lead's reply) go to the "Email" topic; everything
# else (errors, campaign/sourcing status) goes to "Logs" — see
# OrgSettings.telegram_email_topic_id/telegram_logs_topic_id. Both are
# optional: if unset, message_thread_id is omitted and Telegram posts to the
# chat's main stream (a plain group, or a forum's General topic).
EMAIL_TOPIC_TYPES = {"email_sent", "reply_received", "reply_unmatched"}

# These are built as a self-contained "card": a bold <b> heading, a blank
# line under it, then HTML-escaped fields (see send_report_service.py and
# reply_service.py, which escape every dynamic value themselves) — so they
# get HTML parse_mode, and skip the generic level emoji prefix since the
# heading already gives the message its own visual anchor. Every other type
# is free-form, unescaped text, so parse_mode stays off for those to avoid
# Telegram rejecting a message over a stray "<"/"&".
CARD_TYPES = {"email_sent", "reply_received", "reply_unmatched"}


def push_notifications(config, report_pushed_fn):
    token = config.get("telegram_bot_token")
    chat_id = config.get("telegram_chat_id")
    email_topic_id = config.get("telegram_email_topic_id")
    logs_topic_id = config.get("telegram_logs_topic_id")
    pending = config.get("pending_notifications") or []
    if not token or not chat_id or not pending:
        return

    pushed_ids = []
    for notification in pending:
        is_card = notification.get("type") in CARD_TYPES
        text = notification["message"] if is_card else f"{LEVEL_EMOJI.get(notification['level'], 'ℹ️')} {notification['message']}"
        payload = {"chat_id": chat_id, "text": text}
        if is_card:
            payload["parse_mode"] = "HTML"
        topic_id = email_topic_id if notification.get("type") in EMAIL_TOPIC_TYPES else logs_topic_id
        if topic_id:
            payload["message_thread_id"] = topic_id
        try:
            requests.post(
                TELEGRAM_API.format(token=token),
                json=payload,
                timeout=10,
            )
            pushed_ids.append(notification["id"])
        except requests.RequestException as e:
            print(f"Failed to push notification {notification['id']} to Telegram: {e}")

    if pushed_ids:
        try:
            report_pushed_fn(pushed_ids)
        except requests.RequestException as e:
            print(f"Failed to report pushed notifications to Django: {e}")


def push_error(config, source, message):
    """Immediate, direct Telegram push for a worker-side exception (see
    main.py's per-task try/except blocks) — unlike push_notifications above,
    this doesn't go through Django's Notification queue first: the worker
    already has the bot token/chat_id right here (from this same poll's
    config) and its own internet access, so there's nothing to gain from a
    round trip through Django before reporting it. Best-effort — a Telegram
    outage must never raise and interrupt the worker loop."""
    token = config.get("telegram_bot_token")
    chat_id = config.get("telegram_chat_id")
    if not token or not chat_id:
        return
    payload = {"chat_id": chat_id, "text": f"❌ {source}: {message}"}
    logs_topic_id = config.get("telegram_logs_topic_id")
    if logs_topic_id:
        payload["message_thread_id"] = logs_topic_id
    try:
        requests.post(TELEGRAM_API.format(token=token), json=payload, timeout=10)
    except requests.RequestException as e:
        print(f"Failed to push error to Telegram: {e}")
