"""Shared embedding client — the one seam between the index pipeline
(todos/indexing.py) and the query pipeline (todos/retrieval.py). Both
directions of the RAG pipeline must embed text with the same model, so
this is a single function used both to embed document chunks at index
time and to embed the incoming question at query time.
"""
from django.conf import settings

from .openrouter import OPENROUTER_EMBEDDINGS_URL, AIServiceError, _post_json_with_retries


def embed_texts(texts):
    """Embed a batch of texts via OpenRouter's OpenAI-compatible
    /embeddings endpoint. Returns a list of float-vectors in the same
    order as `texts`. Used both to index a document's chunks
    (todos/indexing.py) and to embed an incoming chat message at query
    time (todos/retrieval.py)."""
    if not settings.OPENROUTER_API_KEY:
        raise AIServiceError('AI generation is not configured on this server.')
    if not texts:
        return []

    response = _post_json_with_retries(
        OPENROUTER_EMBEDDINGS_URL,
        {'model': settings.OPENROUTER_EMBEDDING_MODEL, 'input': texts, 'encoding_format': 'float'},
    )
    if response.status_code == 429:
        raise AIServiceError('The AI models are rate-limited right now. Please try again shortly.')
    if not response.ok:
        raise AIServiceError('The AI service returned an error while embedding text.')

    try:
        data = response.json()['data']
        # The API doesn't guarantee `data` preserves input order — sort by
        # the `index` field it returns per embedding.
        return [item['embedding'] for item in sorted(data, key=lambda item: item['index'])]
    except (ValueError, KeyError, TypeError):
        raise AIServiceError('The AI service returned an unexpected response.')
