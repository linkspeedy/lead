import os
import sys
from email.message import EmailMessage
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import email_sender


def _mime():
    msg = EmailMessage()
    msg["Subject"] = "Hi"
    msg["From"] = "sender@test.com"
    msg["To"] = "lead@test.com"
    msg.set_content("Hello")
    return msg


@patch("email_sender.smtplib.SMTP")
def test_send_success(mock_smtp_cls):
    mock_server = MagicMock()
    mock_server.send_message.return_value = {}  # no refused recipients
    mock_smtp_cls.return_value = mock_server

    config = {"host": "smtp.test", "port": 587, "username": "u", "password": "p", "use_tls": True, "use_ssl": False}
    success, response, error, is_connection_error = email_sender.send(_mime(), config)

    assert success is True
    assert error is None
    assert is_connection_error is False
    mock_server.starttls.assert_called_once()
    mock_server.login.assert_called_once_with("u", "p")


@patch("email_sender.smtplib.SMTP")
def test_send_failure_returns_error_not_exception(mock_smtp_cls):
    mock_smtp_cls.side_effect = Exception("connection refused")

    config = {"host": "smtp.test", "port": 587, "username": "u", "password": "p", "use_tls": True, "use_ssl": False}
    success, response, error, is_connection_error = email_sender.send(_mime(), config)

    assert success is False
    assert "connection refused" in error
    # Any raised exception (timeout, DNS failure, auth error, dropped
    # connection, ...) means WE failed to complete the SMTP transaction —
    # not that the recipient's address is bad — so it's a connection error.
    assert is_connection_error is True


@patch("email_sender.smtplib.SMTP")
def test_send_refused_recipient_is_failure_not_connection_error(mock_smtp_cls):
    mock_server = MagicMock()
    mock_server.send_message.return_value = {"lead@test.com": (550, b"mailbox unavailable")}
    mock_smtp_cls.return_value = mock_server

    config = {"host": "smtp.test", "port": 587, "username": "u", "password": "p", "use_tls": True, "use_ssl": False}
    success, response, error, is_connection_error = email_sender.send(_mime(), config)

    assert success is False
    assert "refused" in error.lower()
    # We DID complete a real SMTP session and the server explicitly refused
    # this recipient — the one case that genuinely means "bad address".
    assert is_connection_error is False
