"""The RAG index pipeline: extract text from an upload -> chunk it -> embed
each chunk (via todos/embeddings.py) -> store DocumentChunk rows. See
todos/retrieval.py for the other half of the RAG pipeline (query time).

Uploaded files are never served back over a URL — see DocumentSerializer's
write-only `file` field and the absence of a `media/` route in
config/urls.py. The only things ever done with uploaded content are a
UTF-8 decode/pypdf extraction and template/JSON auto-escaping — never
execution, never unescaped HTML.
"""
import re
import threading

import pypdf
from django.db import connection

from .embeddings import embed_texts
from .models import Document, DocumentChunk
from .openrouter import AIServiceError

ALLOWED_EXTENSIONS = {'txt', 'md', 'pdf'}
MAX_UPLOAD_SIZE = 5 * 1024 * 1024  # 5MB — plenty for notes/a PDF chapter

# ~400-token chunks at ~4 chars/token, ~12.5% overlap, per the RAG deck's
# rules of thumb — expressed in characters since nothing here tokenizes.
CHUNK_SIZE_CHARS = 1600
CHUNK_OVERLAP_CHARS = 200

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
    """Extract -> chunk -> embed -> persist. Never raises: a bad file or
    embedding failure fails the Document (status='failed', error_message
    set), not the caller. Called on a background thread via
    enqueue_indexing() below, not inline in the upload request."""
    document.status = 'processing'
    document.save(update_fields=['status'])

    try:
        with document.file.open('rb') as fh:
            text = extract_text(fh, document.file_type)
    except Exception as exc:  # noqa: BLE001 — extraction can raise many exception types on malformed input; any of them should fail the document, not the caller.
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


def _run_indexing(document_id):
    """Thread target for enqueue_indexing(): re-fetch the Document by pk —
    a model instance/DB connection opened on the request thread must never
    be reused on another thread — run the index pipeline, then close this
    thread's own DB connection. Django only auto-closes connections at the
    end of an HTTP request (via the request_finished signal); a bare
    background thread has no such hook, so skipping this leaks one SQLite
    connection per upload."""
    document = Document.objects.get(pk=document_id)
    try:
        index_document(document)
    finally:
        connection.close()


def enqueue_indexing(document_id):
    """Kick off indexing on a daemon background thread instead of blocking
    the upload request. Known v1 limitation, not a production pattern:
    this app has no Celery/Redis, and a thread's in-flight work is lost if
    the server process restarts mid-index (the Document is left stuck in
    'processing' — acceptable for a learning app; a durable task queue is
    the natural production upgrade). Tests monkeypatch this function to
    run indexing inline/synchronously — see todos/api/tests.py."""
    threading.Thread(target=_run_indexing, args=(document_id,), daemon=True).start()
