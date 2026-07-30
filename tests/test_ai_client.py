import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ai_client


@patch("ai_client.requests.post")
def test_generate_text_success(mock_post):
    mock_post.return_value = MagicMock(
        status_code=200, ok=True,
        json=lambda: {"choices": [{"message": {"content": " Great work on your business! "}}]},
    )
    text, error, is_key_error, is_connection_error = ai_client.generate_text("prompt", "sk-test", "some/model")
    assert text == "Great work on your business!"
    assert error is None
    assert is_key_error is False
    assert is_connection_error is False


@patch("ai_client.requests.post")
def test_generate_text_key_error(mock_post):
    mock_post.return_value = MagicMock(status_code=401, ok=False, text="Unauthorized")
    text, error, is_key_error, is_connection_error = ai_client.generate_text("prompt", "sk-bad", "some/model")
    assert text is None
    assert is_key_error is True
    assert is_connection_error is False
    assert "401" in error


@patch("ai_client.requests.post")
def test_generate_text_other_error(mock_post):
    mock_post.return_value = MagicMock(status_code=500, ok=False, text="Server error")
    text, error, is_key_error, is_connection_error = ai_client.generate_text("prompt", "sk-test", "some/model")
    assert text is None
    assert is_key_error is False
    assert is_connection_error is False
    assert "500" in error


@patch("ai_client.requests.post")
def test_generate_text_null_content_does_not_crash(mock_post):
    """Some free/auto-routed models return a null content field (moderation
    refusal, routing hiccup) on an otherwise-200 response — this must be a
    normal retryable error, not an unhandled AttributeError."""
    mock_post.return_value = MagicMock(
        status_code=200, ok=True,
        json=lambda: {"choices": [{"message": {"content": None}}]},
    )
    text, error, is_key_error, is_connection_error = ai_client.generate_text("prompt", "sk-test", "some/model")
    assert text is None
    assert is_key_error is False
    assert is_connection_error is False
    assert "empty completion" in error


@patch("ai_client.requests.post")
def test_generate_text_connection_error(mock_post):
    """A failure to even reach OpenRouter (DNS/timeout/connection reset) is
    flagged distinctly — Django doesn't count this toward a lead's give-up
    threshold, since it's not a real response from the API at all."""
    import requests
    mock_post.side_effect = requests.exceptions.ConnectionError("getaddrinfo failed")

    text, error, is_key_error, is_connection_error = ai_client.generate_text("prompt", "sk-test", "some/model")
    assert text is None
    assert is_key_error is False
    assert is_connection_error is True
    assert "getaddrinfo failed" in error


@patch("ai_client.requests.post")
def test_generate_text_error_wrapped_in_200_response_is_treated_as_connection_error(mock_post):
    """OpenRouter free-tier/auto-routed models occasionally return HTTP 200
    with an {"error": ...} body instead of a real error status (seen in
    production as 'Unexpected OpenRouter response shape: 'choices'' before
    this was handled) - a provider-side routing hiccup, not a real content
    failure, so it shouldn't consume a lead's give-up attempt either."""
    mock_post.return_value = MagicMock(
        status_code=200, ok=True,
        json=lambda: {"error": {"message": "Provider returned error", "code": 500}},
    )
    text, error, is_key_error, is_connection_error = ai_client.generate_text("prompt", "sk-test", "some/model")
    assert text is None
    assert is_key_error is False
    assert is_connection_error is True
    assert "Provider returned error" in error


@patch("ai_client.requests.post")
def test_generate_text_missing_choices_key_includes_raw_body(mock_post):
    """A genuinely malformed 200 response (no 'choices', no 'error') is a
    real, non-retryable shape problem - but the raw body must be included
    in the error so it's actually diagnosable from a worker log, unlike the
    old bare `KeyError` repr."""
    mock_post.return_value = MagicMock(
        status_code=200, ok=True,
        json=lambda: {"unexpected": "shape"},
        text='{"unexpected": "shape"}',
    )
    text, error, is_key_error, is_connection_error = ai_client.generate_text("prompt", "sk-test", "some/model")
    assert text is None
    assert is_key_error is False
    assert is_connection_error is False
    assert "'choices'" in error
    assert '{"unexpected": "shape"}' in error


@patch("ai_client.requests.post")
def test_generate_text_defaults_to_openrouter_url(mock_post):
    """provider is optional (defaults to openrouter) so existing callers/
    configs that predate multi-provider support keep working unchanged."""
    mock_post.return_value = MagicMock(
        status_code=200, ok=True,
        json=lambda: {"choices": [{"message": {"content": "hi"}}]},
    )
    ai_client.generate_text("prompt", "sk-test", "some/model")
    called_url = mock_post.call_args[0][0]
    assert called_url == ai_client.PROVIDER_URLS["openrouter"]


@patch("ai_client.requests.post")
def test_generate_text_groq_provider_hits_groq_url(mock_post):
    """AIConfig.provider="groq" (the new default - see core/models.py) must
    route the call to Groq's OpenAI-compatible endpoint, not OpenRouter's."""
    mock_post.return_value = MagicMock(
        status_code=200, ok=True,
        json=lambda: {"choices": [{"message": {"content": "hi"}}]},
    )
    text, error, is_key_error, is_connection_error = ai_client.generate_text(
        "prompt", "gsk-test", "llama-3.3-70b-versatile", provider="groq"
    )
    called_url = mock_post.call_args[0][0]
    assert called_url == "https://api.groq.com/openai/v1/chat/completions"
    assert text == "hi"
    assert error is None


@patch("ai_client.requests.post")
def test_generate_text_rate_limited_is_treated_as_connection_error(mock_post):
    """A 429 (rate-limited — common on free-tier models sharing upstream
    capacity, seen in production) is a transient, retryable problem, not a
    real content or auth failure — grouped with is_connection_error so it
    doesn't count toward a lead's give-up threshold either."""
    mock_post.return_value = MagicMock(status_code=429, ok=False, text="rate-limited upstream")
    text, error, is_key_error, is_connection_error = ai_client.generate_text("prompt", "sk-test", "some/model")
    assert text is None
    assert is_key_error is False
    assert is_connection_error is True
    assert "429" in error
