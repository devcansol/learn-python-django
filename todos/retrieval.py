"""The RAG query pipeline: embed the user's message, rank stored chunks by
cosine similarity, brute-force, in pure Python — no numpy, no vector DB.
That's a deliberate choice, not an oversight: at this app's scale (a
personal knowledge base of maybe a few hundred chunks) a hand-rolled
dot-product loop is both fast enough and, per this codebase's existing
style (see todos/openrouter.py's hand-rolled SSE-adjacent retry logic),
*is* the lesson rather than a workaround worth hiding behind a library.

See todos/indexing.py for the other half of the RAG pipeline (index time).
"""
import math

from .embeddings import embed_texts
from .models import DocumentChunk

TOP_K = 5
MIN_SIMILARITY_SCORE = 0.1  # floor on the metric we already compute — discards obvious noise before MMR ever sees the set

CANDIDATE_POOL_SIZE = 20   # widen past TOP_K before diversity re-ranking so MMR has something to trade off against
MMR_LAMBDA = 0.5           # 1.0 = pure relevance, 0.0 = pure diversity; 0.5 balances both


def _cosine_similarity(vec_a, vec_b):
    """Cosine similarity between two equal-length float vectors, by hand —
    dot product over the product of magnitudes."""
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    mag_a = math.sqrt(sum(a * a for a in vec_a))
    mag_b = math.sqrt(sum(b * b for b in vec_b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def _mmr_rerank(scored_chunks, top_k, lambda_param=MMR_LAMBDA):
    """Greedily select up to top_k (chunk, score) pairs from scored_chunks
    (already sorted, highest relevance first), balancing relevance against
    redundancy with chunks already picked — Carbonell & Goldstein's
    Maximal Marginal Relevance. Reuses _cosine_similarity for both the
    relevance term (already computed, passed in) and the diversity term
    (chunk-to-chunk), so no new dependency. Returns the original (chunk,
    relevance) tuples unchanged — MMR decides selection order, not the
    score shown to the caller."""
    if not scored_chunks:
        return []
    remaining = list(scored_chunks)
    selected = []

    def mmr_score(pair):
        chunk, relevance = pair
        if not selected:
            return relevance
        redundancy = max(_cosine_similarity(chunk.embedding, s_chunk.embedding) for s_chunk, _ in selected)
        return lambda_param * relevance - (1 - lambda_param) * redundancy

    while remaining and len(selected) < top_k:
        best = max(remaining, key=mmr_score)
        remaining.remove(best)
        selected.append(best)
    return selected


def retrieve_relevant_chunks(user, query, top_k=TOP_K):
    """Rank every DocumentChunk owned by `user`, across all their
    documents (a global personal knowledge base, not project-scoped), by
    cosine similarity to `query`, then re-rank the top candidates for
    diversity via MMR. Returns (chunk, score) pairs, filtered to a minimum
    relevance floor."""
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
    candidates = scored[:CANDIDATE_POOL_SIZE]
    return _mmr_rerank(candidates, top_k=top_k)


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
