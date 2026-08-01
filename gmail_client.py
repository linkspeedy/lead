"""Gmail API transport, used instead of raw SMTP/IMAP for any SMTPConfig/
IMAPConfig that carries an oauth_refresh_token (see email_sender.py and
reply_checker.py, which branch here) — Render's free tier blocks outbound
SMTP/IMAP sockets entirely, but plain HTTPS calls work fine, same as every
other worker->third-party call (ai_client.py, google_places_client.py).

Client ID/secret live only as this process's env vars (GOOGLE_OAUTH_CLIENT_ID/
GOOGLE_OAUTH_CLIENT_SECRET) — Django never sees them, only the resulting
refresh token (see core/api_views.py gmail_oauth_complete)."""

import base64
import email
import os

import requests
from dotenv import load_dotenv

from email_parsing import build_payload

load_dotenv()

CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "")
TOKEN_URL = "https://oauth2.googleapis.com/token"
GMAIL_API = "https://gmail.googleapis.com/gmail/v1/users/me"
TIMEOUT = 30


def _get_access_token(refresh_token):
    resp = requests.post(TOKEN_URL, data={
        "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
        "refresh_token": refresh_token, "grant_type": "refresh_token",
    }, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()["access_token"]


def get_profile_email(access_token):
    resp = requests.get(f"{GMAIL_API}/profile", headers={"Authorization": f"Bearer {access_token}"}, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()["emailAddress"]


def send(mime_message, config):
    """Same (success, response_text, error_text, is_connection_error)
    contract as email_sender.send — see that module for what each field
    means to the caller."""
    try:
        access_token = _get_access_token(config["oauth_refresh_token"])
        raw = base64.urlsafe_b64encode(mime_message.as_bytes()).decode()
        resp = requests.post(
            f"{GMAIL_API}/messages/send",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"raw": raw}, timeout=TIMEOUT,
        )
        resp.raise_for_status()
        return True, f"Accepted for {mime_message['To']}", None, False
    except Exception as e:
        return False, "", str(e), True


def check_replies(config, report_fn):
    """Mirrors reply_checker.check_replies: forwards every unread message to
    Django, marking it read only after a successful report. Gmail's label
    model doesn't map cleanly onto IMAP folders, so this always reads the
    inbox rather than respecting imap_config['folder']."""
    try:
        access_token = _get_access_token(config["oauth_refresh_token"])
    except Exception as e:
        print(f"Gmail token refresh failed: {e}")
        return

    headers = {"Authorization": f"Bearer {access_token}"}
    try:
        resp = requests.get(f"{GMAIL_API}/messages", headers=headers,
                             params={"q": "is:unread in:inbox"}, timeout=TIMEOUT)
        resp.raise_for_status()
        message_ids = [m["id"] for m in resp.json().get("messages", [])]
    except Exception as e:
        print(f"Gmail message list failed: {e}")
        return

    for msg_id in message_ids:
        try:
            resp = requests.get(f"{GMAIL_API}/messages/{msg_id}", headers=headers,
                                 params={"format": "raw"}, timeout=TIMEOUT)
            resp.raise_for_status()
            raw = resp.json()["raw"]
            raw += "=" * (-len(raw) % 4)  # restore padding urlsafe_b64encode strips
            message = email.message_from_bytes(base64.urlsafe_b64decode(raw))
            payload = build_payload(message)
        except Exception as e:
            print(f"Failed to fetch/parse Gmail message {msg_id}: {e}")
            continue

        try:
            report_fn(payload)
            requests.post(f"{GMAIL_API}/messages/{msg_id}/modify", headers=headers,
                          json={"removeLabelIds": ["UNREAD"]}, timeout=TIMEOUT).raise_for_status()
        except Exception as e:
            print(f"Failed to report reply {payload.get('message_id')}: {e}")
