"""Document ingestion + retrieval for the RAG-powered chat widget.

Pipeline: extract text from an upload -> chunk it -> embed each chunk (via
todos/ai.py) -> store DocumentChunk rows. At query time: embed the user's
message and rank stored chunks by cosine similarity, brute-force, in pure
Python — no numpy, no vector DB. That's a deliberate choice, not an
oversight: at this app's scale (a personal knowledge base of maybe a few
hundred chunks) a hand-rolled dot-product loop is both fast enough and, per
this codebase's existing style (see todos/ai.py's hand-rolled SSE parsing),
*is* the lesson rather than a workaround worth hiding behind a library.

Uploaded files are never served back over a URL — see DocumentSerializer's
write-only `file` field and the absence of a `media/` route in
config/urls.py. The only things ever done with uploaded content are a
UTF-8 decode/pypdf extraction and template/JSON auto-escaping — never
execution, never unescaped HTML.
"""
import math
import re

import pypdf

from .ai import AIServiceError, embed_texts
from .models import DocumentChunk

ALLOWED_EXTENSIONS = {'txt', 'md', 'pdf'}
MAX_UPLOAD_SIZE = 5 * 1024 * 1024  # 5MB — plenty for notes/a PDF chapter, small enough to keep synchronous indexing fast

# ~400-token chunks at ~4 chars/token, ~12.5% overlap, per the RAG deck's
# rules of thumb — expressed in characters since nothing here tokenizes.
CHUNK_SIZE_CHARS = 1600
CHUNK_OVERLAP_CHARS = 200

TOP_K = 5
MIN_SIMILARITY_SCORE = 0.1  # floor on the metric we already compute — not a re-ranking pass, just discarding obvious noise

PARAGRAPH_SPLIT_RE = re.compile(r'\n\s*\n+')
SENTENCE_SPLIT_RE = re.compile(r'(?<=[.!?])\s+')


def extract_text(fh, file_type):
    """Pull plain text out of an open, binary file-like object. May raise
    on a malformed file — the caller (index_document) turns that into
    status='failed' instead of a 500, since an uploaded file's contents
    can't be trusted to be well-formed just because its extension says
    so."""
    if file_type in ('txt', 'md'):
        return fh.read().decode('utf-8', errors='replace')
    if file_type == 'pdf':
        reader = pypdf.PdfReader(fh)
        return '\n\n'.join((page.extract_text() or '') for page in reader.pages)
    raise ValueError(f'Unsupported file type: {file_type!r}')


def _split_into_units(text, max_unit_size):
    """Recursively break text into units no larger than max_unit_size: try
    paragraphs first, fall back to sentences for any paragraph that's
    still too big, fall back to a hard character cut for any sentence
    that's still too big (e.g. one giant unbroken line)."""
    units = []
    for para in PARAGRAPH_SPLIT_RE.split(text.strip()):
        para = para.strip()
        if not para:
            continue
        if len(para) <= max_unit_size:
            units.append(para)
            continue
        for sentence in SENTENCE_SPLIT_RE.split(para):
            sentence = sentence.strip()
            if not sentence:
                continue
            if len(sentence) <= max_unit_size:
                units.append(sentence)
            else:
                for i in range(0, len(sentence), max_unit_size):
                    units.append(sentence[i:i + max_unit_size])
    return units


def chunk_text(text, chunk_size=CHUNK_SIZE_CHARS, overlap=CHUNK_OVERLAP_CHARS):
    """Greedily pack small units into ~chunk_size windows, carrying the
    trailing `overlap` characters of each chunk into the start of the next
    so a fact split across a boundary still appears whole in at least one
    chunk."""
    chunks = []
    current = ''
    for unit in _split_into_units(text, chunk_size):
        candidate = f'{current} {unit}'.strip() if current else unit
        if len(candidate) <= chunk_size or not current:
            current = candidate
        else:
            chunks.append(current)
            tail = current[-overlap:] if overlap else ''
            current = f'{tail} {unit}'.strip()
    if current:
        chunks.append(current)
    return chunks


def index_document(document):
    """Extract -> chunk -> embed -> persist, synchronously, inline in the
    upload request (this app has no Celery/background workers — a known
    v1 simplification; a task queue triggered on upload is the natural
    production upgrade). Never raises: a bad file or embedding failure
    fails the Document (status='failed', error_message set), not the HTTP
    request."""
    document.status = 'processing'
    document.save(update_fields=['status'])

    try:
        with document.file.open('rb') as fh:
            text = extract_text(fh, document.file_type)
    except Exception as exc:  # noqa: BLE001 — extraction can raise many exception types on malformed input; any of them should fail the document, not the request.
        document.status = 'failed'
        document.error_message = f'Could not read the file: {exc}'
        document.save(update_fields=['status', 'error_message'])
        return document

    text = text.strip()
    if not text:
        document.status = 'failed'
        document.error_message = 'No text could be extracted from this file (e.g. a scanned PDF with no text layer).'
        document.save(update_fields=['status', 'error_message'])
        return document

    pieces = chunk_text(text)
    try:
        embeddings = embed_texts(pieces)
    except AIServiceError as exc:
        document.status = 'failed'
        document.error_message = str(exc)
        document.save(update_fields=['status', 'error_message'])
        return document

    DocumentChunk.objects.bulk_create([
        DocumentChunk(document=document, chunk_index=i, text=piece, embedding=embedding)
        for i, (piece, embedding) in enumerate(zip(pieces, embeddings))
    ])

    document.status = 'completed'
    document.char_count = len(text)
    document.chunk_count = len(pieces)
    document.error_message = ''
    document.save(update_fields=['status', 'char_count', 'chunk_count', 'error_message'])
    return document


def _cosine_similarity(vec_a, vec_b):
    """Cosine similarity between two equal-length float vectors, by hand —
    dot product over the product of magnitudes."""
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    mag_a = math.sqrt(sum(a * a for a in vec_a))
    mag_b = math.sqrt(sum(b * b for b in vec_b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def retrieve_relevant_chunks(user, query, top_k=TOP_K):
    """Rank every DocumentChunk owned by `user`, across all their
    documents (a global personal knowledge base, not project-scoped), by
    cosine similarity to `query`. Returns (chunk, score) pairs, highest
    first, filtered to a minimum relevance floor."""
    chunks = list(
        DocumentChunk.objects.filter(document__owner=user, document__status='completed')
        .select_related('document')
    )
    if not chunks:
        return []  # no embed_texts call at all — zero extra latency/cost for users who never upload a document

    query_vector = embed_texts([query])[0]
    scored = [(chunk, _cosine_similarity(query_vector, chunk.embedding)) for chunk in chunks]
    scored = [pair for pair in scored if pair[1] >= MIN_SIMILARITY_SCORE]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored[:top_k]


def build_retrieved_context(scored_chunks):
    """Render (chunk, score) pairs into the text that becomes
    stream_answer's <retrieved_documents> block, tagged with source
    document title + chunk index for provenance. Empty string (not a
    filler sentence) when there's nothing relevant, so stream_answer omits
    the block entirely."""
    if not scored_chunks:
        return ''
    lines = []
    for chunk, _score in scored_chunks:
        lines.append(f'[Source: {chunk.document.title}, chunk {chunk.chunk_index}]')
        lines.append(chunk.text)
        lines.append('')
    return '\n'.join(lines).strip()
