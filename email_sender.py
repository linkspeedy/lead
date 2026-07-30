import smtplib


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
    try:
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
