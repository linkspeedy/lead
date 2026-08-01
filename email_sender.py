import smtplib
import socket
from contextlib import contextmanager

import gmail_client


@contextmanager
def _force_ipv4():
    """Render's free tier has no outbound IPv6 route, but DNS lookups for
    mail hosts (Gmail included) often return an IPv6 address first, which
    smtplib then tries and fails on immediately with [Errno 101] Network is
    unreachable. Restrict resolution to IPv4 for just the connection
    attempt so it never picks an unreachable address."""
    original_getaddrinfo = socket.getaddrinfo

    def ipv4_only_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        return original_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)

    socket.getaddrinfo = ipv4_only_getaddrinfo
    try:
        yield
    finally:
        socket.getaddrinfo = original_getaddrinfo


def send(mime_message, smtp_config):
    """Returns (success, response_text, error_text, is_connection_error).
    Never raises — the caller (campaign_processor.py) always has something
    to report back to Django regardless of outcome.

    is_connection_error=True means WE failed to complete the SMTP
    transaction (DNS failure, timeout, connection reset, auth failure,
    dropped connection mid-handshake, etc.) — a transient problem on our
    end, unrelated to whether the recipient's address is any good. False
    means the SMTP server itself explicitly refused the recipient — the one
    case that actually means "this address doesn't work." Django uses this
    to decide whether to retry later or mark the lead bounced (see
    campaigns/services/send_report_service.py)."""
    if smtp_config.get("oauth_refresh_token"):
        return gmail_client.send(mime_message, smtp_config)

    try:
        with _force_ipv4():
            if smtp_config.get("use_ssl"):
                server = smtplib.SMTP_SSL(smtp_config["host"], smtp_config["port"], timeout=30)
            else:
                server = smtplib.SMTP(smtp_config["host"], smtp_config["port"], timeout=30)

        with server:
            if smtp_config.get("use_tls") and not smtp_config.get("use_ssl"):
                server.starttls()
            server.login(smtp_config["username"], smtp_config["password"])
            refused = server.send_message(mime_message)

        if refused:
            return False, "", f"Recipients refused: {refused}", False
        return True, f"250 Accepted for {mime_message['To']}", None, False
    except Exception as e:
        return False, "", str(e), True
