"""Relays Django-created Notification rows to Telegram. Independent of
SMTP/email on purpose — an alert like "your SMTP config is broken" must not
depend on the very channel it's reporting as broken. Best-effort: a
Telegram outage must never interrupt sending or AI processing."""

import requests

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"

LEVEL_EMOJI = {"info": "ℹ️", "warning": "⚠️", "error": "❌"}


def push_notifications(config, report_pushed_fn):
    token = config.get("telegram_bot_token")
    chat_id = config.get("telegram_chat_id")
    pending = config.get("pending_notifications") or []
    if not token or not chat_id or not pending:
        return

    pushed_ids = []
    for notification in pending:
        emoji = LEVEL_EMOJI.get(notification["level"], "ℹ️")
        payload = {"chat_id": chat_id, "text": f"{emoji} {notification['message']}"}
        if notification.get("type") == "email_sent":
            # Only this notification type is built with a literal <b> tag
            # (see send_report_service.py, which HTML-escapes every dynamic
            # field itself) — every other type sends free-form text that
            # was never escaped for HTML, so parse_mode stays off for those
            # to avoid Telegram rejecting a message over a stray "<"/"&".
            payload["parse_mode"] = "HTML"
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
    try:
        requests.post(
            TELEGRAM_API.format(token=token),
            json={"chat_id": chat_id, "text": f"❌ {source}: {message}"},
            timeout=10,
        )
    except requests.RequestException as e:
        print(f"Failed to push error to Telegram: {e}")
