import os
from threading import Thread
from urllib.parse import urlencode

import requests
from flask import Flask, redirect, request

import api_client
import gmail_client

app = Flask('')

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GMAIL_OAUTH_SCOPES = "https://www.googleapis.com/auth/gmail.send https://www.googleapis.com/auth/gmail.modify"


@app.route('/')
def home():
    return "Outreach worker is alive and running!"


@app.route('/oauth2start')
def oauth2_start():
    """Linked from the dashboard's "Connect Gmail Account" button. Django
    can't build/host this redirect itself in the usual way since the token
    exchange in /oauth2callback below needs outbound access Django doesn't
    have on PythonAnywhere — so the whole OAuth handshake happens here on
    the worker instead, which already talks to third-party HTTPS APIs
    unrestricted (see gmail_client.py)."""
    client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "")
    if not client_id:
        return "GOOGLE_OAUTH_CLIENT_ID is not set on this worker.", 500

    redirect_uri = request.host_url.rstrip('/') + '/oauth2callback'
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": GMAIL_OAUTH_SCOPES,
        "access_type": "offline",
        "prompt": "consent",
    }
    return redirect(f"{GOOGLE_AUTH_URL}?{urlencode(params)}")


@app.route('/oauth2callback')
def oauth2_callback():
    """Exchanges Google's authorization code for a refresh token, then
    reports it to Django (core.api_views.gmail_oauth_complete) over the same
    worker->Django channel every other worker action already uses."""
    error = request.args.get('error')
    if error:
        return f"Google OAuth error: {error}", 400

    code = request.args.get('code')
    if not code:
        return "Missing authorization code.", 400

    redirect_uri = request.host_url.rstrip('/') + '/oauth2callback'
    try:
        resp = requests.post("https://oauth2.googleapis.com/token", data={
            "client_id": os.getenv("GOOGLE_OAUTH_CLIENT_ID", ""),
            "client_secret": os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", ""),
            "code": code,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }, timeout=30)
        resp.raise_for_status()
        tokens = resp.json()

        refresh_token = tokens.get("refresh_token")
        if not refresh_token:
            return (
                "Google didn't return a refresh token (it only issues one on first "
                "consent). Revoke access at https://myaccount.google.com/permissions "
                "and try connecting again."
            ), 400

        email_address = gmail_client.get_profile_email(tokens["access_token"])
        api_client.report_gmail_oauth_complete(refresh_token, email_address)
    except Exception as e:
        return f"Failed to complete Gmail connection: {e}", 500

    return f"Gmail connected: {email_address}. You can close this tab and return to the dashboard."


def run():
    # Render binds dynamic ports via the PORT environment variable.
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)


def keep_alive():
    t = Thread(target=run)
    t.start()
