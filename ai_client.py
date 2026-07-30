"""Proxies one chat-completion call to whichever provider AIConfig.provider
selects. Django decides WHAT to ask (the prompt, built in
campaigns/services/ai_personalization_service.py from lead data), WHETHER
personalization is needed at all, and WHICH provider/model to use — this
module only executes the HTTP call, because Django (on PythonAnywhere's free
tier) can't reach either provider directly. It never decides business
logic."""

import requests

# Both providers expose an OpenAI-compatible chat/completions endpoint
# (same request body shape, same {"choices": [{"message": {"content": ...}}]}
# response shape, same Bearer auth) - only the base URL differs.
PROVIDER_URLS = {
    "openrouter": "https://openrouter.ai/api/v1/chat/completions",
    "groq": "https://api.groq.com/openai/v1/chat/completions",
}
KEY_ERROR_STATUS_CODES = (401, 402, 403)
RATE_LIMIT_STATUS_CODE = 429


def generate_text(prompt, api_key, model, provider="openrouter"):
    """Returns (text, error, is_key_error, is_connection_error).

    is_key_error=True means an auth/credit-shaped response (401/402/403).
    Seen in production on OpenRouter: a 401 "Missing Authentication header"
    with a confirmed-present, correctly-formatted key — almost certainly a
    transient upstream gateway issue on the free-tier provider, not an
    actually-bad key. Django flags this in a notification but does NOT
    auto-disable the config over it (see ai_personalization_service.py) —
    config changes only happen when the user edits Settings themselves.

    is_connection_error=True means a transient, retryable problem that
    isn't a real content/auth failure: either we failed to even reach the
    provider (DNS failure, timeout, connection reset), it responded 429
    (rate-limited - common on free tiers, which share upstream capacity),
    or it wrapped an error inside an otherwise-200 response (seen on
    OpenRouter's free-tier routing). Django doesn't count any of these
    toward a lead's give-up threshold, since retrying is very likely to
    just work once the blip/rate-limit window clears."""
    url = PROVIDER_URLS.get(provider, PROVIDER_URLS["openrouter"])

    try:
        resp = requests.post(
            url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                # Generates a full subject + email body now, not just a
                # one-line opening — 120 was tuned for the old single-line
                # output and would truncate a real body mid-sentence.
                "max_tokens": 350,
            },
            timeout=30,
        )
    except requests.RequestException as e:
        return None, str(e), False, True

    if resp.status_code == RATE_LIMIT_STATUS_CODE:
        return None, f"{resp.status_code}: {resp.text[:300]}", False, True

    if resp.status_code in KEY_ERROR_STATUS_CODES:
        return None, f"{resp.status_code}: {resp.text[:300]}", True, False

    if not resp.ok:
        return None, f"{resp.status_code}: {resp.text[:300]}", False, False

    try:
        data = resp.json()
    except ValueError as e:
        return None, f"Unexpected {provider} response shape: {e}. Raw: {resp.text[:300]}", False, False

    if isinstance(data, dict) and "error" in data:
        # Free-tier/auto-routed models occasionally wrap an error inside an
        # HTTP 200 response (routing failure, provider-side hiccup) instead
        # of returning a real error status - not a real content or auth
        # failure, so treat it like the 429/401 gateway hiccups above:
        # retryable, no attempt consumed.
        err = data["error"]
        message = err.get("message", str(err)) if isinstance(err, dict) else str(err)
        return None, f"{provider} returned an error in a 200 response: {message}", False, True

    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        return None, f"Unexpected {provider} response shape: {e}. Raw: {resp.text[:300]}", False, False

    # Free-tier/auto-routed models occasionally return a null or empty
    # completion (moderation refusal, routing hiccup, etc.) instead of an
    # error status — treat that as a retryable failure rather than crashing
    # with AttributeError on the .strip() below.
    if not content:
        return None, f"{provider} returned an empty completion.", False, False
    return content.strip(), None, False, False
