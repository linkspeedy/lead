import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import reply_checker

RAW_EMAIL = (
    b"From: Jane Lead <jane@acme.test>\r\n"
    b"Subject: Re: Quick question\r\n"
    b"Message-ID: <reply1@gmail.com>\r\n"
    b"In-Reply-To: <original@outreach.local>\r\n"
    b"References: <original@outreach.local>\r\n"
    b"Content-Type: text/plain; charset=utf-8\r\n"
    b"\r\n"
    b"Sure, tell me more.\r\n"
)


@patch("reply_checker.imaplib.IMAP4_SSL")
def test_check_replies_forwards_and_marks_seen(mock_imap_cls):
    mock_conn = MagicMock()
    mock_imap_cls.return_value = mock_conn
    mock_conn.search.return_value = ("OK", [b"1"])
    mock_conn.fetch.return_value = ("OK", [(b"1 (BODY[])", RAW_EMAIL)])

    reported = []
    imap_config = {"host": "imap.test", "port": 993, "username": "u", "password": "p", "use_ssl": True, "folder": "INBOX"}

    reply_checker.check_replies(imap_config, reported.append)

    assert len(reported) == 1
    payload = reported[0]
    assert payload["from_email"] == "jane@acme.test"
    assert payload["message_id"] == "<reply1@gmail.com>"
    assert payload["in_reply_to"] == "<original@outreach.local>"
    assert "tell me more" in payload["body_snippet"]

    mock_conn.store.assert_called_once_with(b"1", "+FLAGS", "\\Seen")
    mock_conn.logout.assert_called_once()


@patch("reply_checker.imaplib.IMAP4_SSL")
def test_check_replies_does_not_mark_seen_on_report_failure(mock_imap_cls):
    mock_conn = MagicMock()
    mock_imap_cls.return_value = mock_conn
    mock_conn.search.return_value = ("OK", [b"1"])
    mock_conn.fetch.return_value = ("OK", [(b"1 (BODY[])", RAW_EMAIL)])

    def failing_report(payload):
        raise ConnectionError("Django unreachable")

    imap_config = {"host": "imap.test", "port": 993, "username": "u", "password": "p", "use_ssl": True}
    reply_checker.check_replies(imap_config, failing_report)

    mock_conn.store.assert_not_called()  # so the same message is re-seen next poll


@patch("reply_checker.imaplib.IMAP4_SSL")
def test_check_replies_noop_when_no_unseen(mock_imap_cls):
    mock_conn = MagicMock()
    mock_imap_cls.return_value = mock_conn
    mock_conn.search.return_value = ("OK", [b""])

    reported = []
    imap_config = {"host": "imap.test", "port": 993, "username": "u", "password": "p", "use_ssl": True}
    reply_checker.check_replies(imap_config, reported.append)

    assert reported == []
