"""Shared OpenRouter HTTP transport: retry/backoff plumbing used by both
todos/ai.py (chat completions) and todos/embeddings.py. Neither of those
modules talks to `requests` directly — they both go through
_post_json_with_retries() here, so there's exactly one place that knows how
to authenticate, retry, and back off against OpenRouter.
"""
import time

import requests
from django.conf import settings

OPENROUTER_URL = 'https://openrouter.ai/api/v1/chat/completions'
OPENROUTER_EMBEDDINGS_URL = 'https://openrouter.ai/api/v1/embeddings'
REQUEST_TIMEOUT = 20
MAX_ATTEMPTS = 3               # per model, on a 5xx
BACKOFF_SECONDS = 0.5          # doubles each retry: 0.5s, 1s
RETRYABLE_STATUS = frozenset({500, 502, 503, 504})
# Falls through to the next model in OPENROUTER_FALLBACK_MODELS on either:
# rate-limited (429), or the model slug itself is gone/deprecated (404) —
# OpenRouter's free-tier catalog rotates models out from under us.
FALLBACK_TRIGGER_STATUS = frozenset({404, 429})


class AIServiceError(Exception):
    """Raised for any failure generating a description, chat reply, or
    embedding; message is safe to show directly to the user."""


def _post_json_with_retries(url, payload, stream=False):
    """POST one payload to `url`, retrying up to MAX_ATTEMPTS times with
    exponential backoff on a 5xx. Returns the requests.Response as-is —
    the caller decides what a 429 or other non-ok status means. Shared by
    the chat-completions and embeddings endpoints."""
    response = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            response = requests.post(
                url,
                headers={
                    'Authorization': f'Bearer {settings.OPENROUTER_API_KEY}',
                    'Content-Type': 'application/json',
                    'HTTP-Referer': 'http://localhost:8000',
                    'X-Title': 'Todo Learning App',
                },
                json=payload,
                timeout=REQUEST_TIMEOUT,
                stream=stream,
            )
        except requests.exceptions.Timeout:
            raise AIServiceError('The AI service timed out. Please try again.')
        except requests.exceptions.RequestException:
            raise AIServiceError('Could not reach the AI service. Please try again.')

        if response.status_code in RETRYABLE_STATUS and attempt < MAX_ATTEMPTS - 1:
            response.close()
            time.sleep(BACKOFF_SECONDS * (2 ** attempt))
            continue
        return response
    return response
