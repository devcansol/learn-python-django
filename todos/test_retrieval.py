from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase

from .models import Document, DocumentChunk
from .retrieval import (
    _cosine_similarity,
    _mmr_rerank,
    build_retrieved_context,
    retrieve_relevant_chunks,
)


class CosineSimilarityTests(TestCase):
    def test_identical_vectors_score_one(self):
        self.assertAlmostEqual(_cosine_similarity([1, 2, 3], [1, 2, 3]), 1.0)

    def test_orthogonal_vectors_score_zero(self):
        self.assertAlmostEqual(_cosine_similarity([1, 0], [0, 1]), 0.0)

    def test_opposite_vectors_score_negative_one(self):
        self.assertAlmostEqual(_cosine_similarity([1, 2], [-1, -2]), -1.0)

    def test_zero_vector_scores_zero_instead_of_dividing_by_zero(self):
        self.assertEqual(_cosine_similarity([0, 0], [1, 2]), 0.0)


class MMRRerankTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user('owner', password='pw12345678')
        self.document = Document.objects.create(owner=self.owner, title='notes.txt', file_type='txt', status='completed')

    def _chunk(self, index, text, embedding):
        return DocumentChunk.objects.create(document=self.document, chunk_index=index, text=text, embedding=embedding)

    def test_pure_relevance_lambda_reproduces_plain_top_k_ordering(self):
        best = self._chunk(0, 'best', [1.0, 0.0])
        middle = self._chunk(1, 'middle', [0.9, 0.1])
        worst = self._chunk(2, 'worst', [0.5, 0.5])
        scored = [(best, 0.99), (middle, 0.9), (worst, 0.5)]

        result = _mmr_rerank(scored, top_k=3, lambda_param=1.0)

        self.assertEqual([chunk for chunk, _score in result], [best, middle, worst])

    def test_diversity_displaces_a_near_duplicate_high_scoring_chunk(self):
        # `near_duplicate` scores highest but points almost the same
        # direction as `top`, already selected first; `distinct` is
        # orthogonal (genuinely different content) despite a lower raw
        # relevance score. A diversity-weighted MMR pass should prefer
        # `distinct` over `near_duplicate` for the second pick.
        top = self._chunk(0, 'top', [1.0, 0.0])
        near_duplicate = self._chunk(1, 'near duplicate', [0.99, 0.01])
        distinct = self._chunk(2, 'distinct', [0.0, 1.0])
        scored = [(top, 0.99), (near_duplicate, 0.95), (distinct, 0.6)]

        result = _mmr_rerank(scored, top_k=2, lambda_param=0.3)

        self.assertEqual([chunk for chunk, _score in result], [top, distinct])

    def test_empty_input_returns_empty_list(self):
        self.assertEqual(_mmr_rerank([], top_k=5), [])


class RetrieveRelevantChunksTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user('owner', password='pw12345678')
        self.other = User.objects.create_user('other', password='pw12345678')

    def _make_completed_document(self, owner, title):
        return Document.objects.create(owner=owner, title=title, file_type='txt', status='completed')

    @mock.patch('todos.retrieval.embed_texts')
    def test_ranks_by_similarity_highest_first(self, mock_embed_texts):
        document = self._make_completed_document(self.owner, 'notes.txt')
        close_chunk = DocumentChunk.objects.create(document=document, chunk_index=0, text='close', embedding=[1, 0])
        far_chunk = DocumentChunk.objects.create(document=document, chunk_index=1, text='far', embedding=[0, 1])
        mock_embed_texts.return_value = [[1, 0]]

        results = retrieve_relevant_chunks(self.owner, 'query')

        self.assertEqual([chunk for chunk, _score in results], [close_chunk])
        self.assertNotIn(far_chunk, [chunk for chunk, _score in results])

    @mock.patch('todos.retrieval.embed_texts')
    def test_only_returns_the_requesting_users_chunks(self, mock_embed_texts):
        own_document = self._make_completed_document(self.owner, 'mine.txt')
        DocumentChunk.objects.create(document=own_document, chunk_index=0, text='mine', embedding=[1, 0])
        other_document = self._make_completed_document(self.other, 'theirs.txt')
        DocumentChunk.objects.create(document=other_document, chunk_index=0, text='theirs', embedding=[1, 0])
        mock_embed_texts.return_value = [[1, 0]]

        results = retrieve_relevant_chunks(self.owner, 'query')

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0].document, own_document)

    @mock.patch('todos.retrieval.embed_texts')
    def test_no_documents_skips_the_embedding_call_entirely(self, mock_embed_texts):
        results = retrieve_relevant_chunks(self.owner, 'query')

        self.assertEqual(results, [])
        mock_embed_texts.assert_not_called()

    @mock.patch('todos.retrieval.embed_texts')
    def test_ignores_chunks_from_documents_still_indexing(self, mock_embed_texts):
        pending_document = Document.objects.create(owner=self.owner, title='pending.txt', file_type='txt', status='processing')
        DocumentChunk.objects.create(document=pending_document, chunk_index=0, text='not ready', embedding=[1, 0])
        mock_embed_texts.return_value = [[1, 0]]

        results = retrieve_relevant_chunks(self.owner, 'query')

        self.assertEqual(results, [])
        mock_embed_texts.assert_not_called()


class BuildRetrievedContextTests(TestCase):
    def test_empty_input_returns_empty_string(self):
        self.assertEqual(build_retrieved_context([]), '')

    def test_renders_source_and_text_for_each_chunk(self):
        owner = User.objects.create_user('owner', password='pw12345678')
        document = Document.objects.create(owner=owner, title='notes.txt', file_type='txt', status='completed')
        chunk = DocumentChunk.objects.create(document=document, chunk_index=2, text='the answer is 42', embedding=[1])

        context = build_retrieved_context([(chunk, 0.9)])

        self.assertIn('notes.txt', context)
        self.assertIn('chunk 2', context)
        self.assertIn('the answer is 42', context)
