"""OpenRouter client for the "Generate with AI" description helper.

Deliberately minimal: no streaming, just a synchronous request/response
round-trip. Tries settings.OPENROUTER_MODEL first, then falls through
settings.OPENROUTER_FALLBACK_MODELS in order if a model is rate-limited.
"""
import requests
from django.conf import settings

OPENROUTER_URL = 'https://openrouter.ai/api/v1/chat/completions'
REQUEST_TIMEOUT = 20


class AIServiceError(Exception):
    """Raised for any failure generating a description; message is safe to
    show directly to the user."""


def generate_description(subject, hint='', parent_context=''):
    if not settings.OPENROUTER_API_KEY:
        raise AIServiceError('AI generation is not configured on this server.')

    instructions = [
        'Write a concise, plain-text description (2-4 sentences, no markdown, no headings).',
        f'Subject: {subject}',
    ]
    if parent_context:
        instructions.append(f'It belongs to: {parent_context}')
    if hint:
        instructions.append(f'Extra guidance from the user: {hint}')

    messages = [
        {
            'role': 'system',
            'content': (
                'You write short, clear descriptions for items in a task-management app. '
                'Respond with only the description text, no preamble or quotes.'
            ),
        },
        {'role': 'user', 'content': '\n'.join(instructions)},
    ]

    models = [settings.OPENROUTER_MODEL, *getattr(settings, 'OPENROUTER_FALLBACK_MODELS', [])]

    response = None
    for model in models:
        try:
            response = requests.post(
                OPENROUTER_URL,
                headers={
                    'Authorization': f'Bearer {settings.OPENROUTER_API_KEY}',
                    'Content-Type': 'application/json',
                    'HTTP-Referer': 'http://localhost:8000',
                    'X-Title': 'Todo Learning App',
                },
                json={
                    'model': model,
                    'messages': messages,
                },
                timeout=REQUEST_TIMEOUT,
            )
        except requests.exceptions.Timeout:
            raise AIServiceError('The AI service timed out. Please try again.')
        except requests.exceptions.RequestException:
            raise AIServiceError('Could not reach the AI service. Please try again.')

        if response.status_code == 429 and model != models[-1]:
            continue
        break

    if response.status_code == 429:
        raise AIServiceError('The AI models are rate-limited right now. Please try again shortly.')
    if not response.ok:
        raise AIServiceError('The AI service returned an error. Please try again.')

    try:
        data = response.json()
        content = data['choices'][0]['message']['content']
    except (ValueError, KeyError, IndexError, TypeError):
        raise AIServiceError('The AI service returned an unexpected response.')

    content = content.strip()
    if not content:
        raise AIServiceError('The AI service returned an empty description.')
    return content
