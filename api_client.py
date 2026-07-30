"""All HTTP calls from the worker to Django live here, so every other
worker module stays free of request/URL/header plumbing. The worker never
decides business logic — it asks Django what to do (fetch_*) and reports
what happened (report_*); see django_app/core/api_views.py and
django_app/campaigns/api_views.py for the corresponding server side."""

import os

import requests
from dotenv import load_dotenv

load_dotenv()

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000/api/worker")
WORKER_API_KEY = os.getenv("WORKER_API_KEY", "")
HEADERS = {"X-Worker-Key": WORKER_API_KEY}
TIMEOUT = 20


def fetch_config():
    resp = requests.get(f"{API_URL}/config/", headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def fetch_sendable():
    resp = requests.get(f"{API_URL}/sendable/", headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def report_email_sent(payload):
    resp = requests.post(f"{API_URL}/email/sent/", headers=HEADERS, json=payload, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def fetch_ai_pending():
    resp = requests.get(f"{API_URL}/ai/pending/", headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def report_ai_completed(payload):
    resp = requests.post(f"{API_URL}/ai/completed/", headers=HEADERS, json=payload, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def report_trigger_complete(trigger_id, status, result=None):
    resp = requests.post(
        f"{API_URL}/triggers/complete/", headers=HEADERS,
        json={"trigger_id": trigger_id, "status": status, "result": result or {}}, timeout=TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def report_notifications_pushed(ids):
    resp = requests.post(f"{API_URL}/notifications/pushed/", headers=HEADERS, json={"ids": ids}, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def report_reply_detected(payload):
    resp = requests.post(f"{API_URL}/replies/detected/", headers=HEADERS, json=payload, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def fetch_lead_sourcing_pending():
    resp = requests.get(f"{API_URL}/leads/sourcing/pending/", headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def report_lead_sourcing_results(payload):
    resp = requests.post(f"{API_URL}/leads/sourcing/results/", headers=HEADERS, json=payload, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()
