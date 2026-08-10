import io
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase

from .models import Document, DocumentChunk
from .rag import (
    _cosine_similarity,
    build_retrieved_context,
    chunk_text,
    extract_text,
    retrieve_relevant_chunks,
)


class ChunkTextTests(TestCase):
    def test_short_text_is_a_single_chunk(self):
        chunks = chunk_text('A short paragraph.', chunk_size=100, overlap=10)
        self.assertEqual(chunks, ['A short paragraph.'])

    def test_long_text_splits_with_overlap(self):
        paragraph_a = 'Sentence one is here. Sentence two is here. Sentence three is here.'
        paragraph_b = 'Sentence four is here. Sentence five is here. Sentence six is here.'
        text = f'{paragraph_a}\n\n{paragraph_b}'

        chunks = chunk_text(text, chunk_size=len(paragraph_a), overlap=20)

        self.assertGreater(len(chunks), 1)
        # The tail of the first chunk should reappear at the start of the
        # second, proving the overlap was actually carried over.
        self.assertIn(chunks[0][-20:].strip(), chunks[1])

    def test_prefers_paragraph_boundary_over_mid_sentence_split(self):
        paragraph_a = 'First paragraph.'
        paragraph_b = 'Second paragraph is long enough to force a split point somewhere.'
        text = f'{paragraph_a}\n\n{paragraph_b}'

        chunks = chunk_text(text, chunk_size=len(paragraph_a) + 1, overlap=0)

        self.assertEqual(chunks[0], paragraph_a)


class ExtractTextTests(TestCase):
    def test_txt_decodes_as_utf8(self):
        fh = io.BytesIO('hello world'.encode('utf-8'))
        self.assertEqual(extract_text(fh, 'txt'), 'hello world')

    def test_md_decodes_as_utf8(self):
        fh = io.BytesIO('# heading'.encode('utf-8'))
        self.assertEqual(extract_text(fh, 'md'), '# heading')

    def test_pdf_joins_page_text(self):
        fake_page_1 = mock.Mock()
        fake_page_1.extract_text.return_value = 'Page one.'
        fake_page_2 = mock.Mock()
        fake_page_2.extract_text.return_value = 'Page two.'

        with mock.patch('todos.rag.pypdf.PdfReader') as mock_reader:
            mock_reader.return_value.pages = [fake_page_1, fake_page_2]
            text = extract_text(io.BytesIO(b'%PDF-fake'), 'pdf')

        self.assertEqual(text, 'Page one.\n\nPage two.')

    def test_unsupported_file_type_raises(self):
        with self.assertRaises(ValueError):
            extract_text(io.BytesIO(b''), 'docx')


class CosineSimilarityTests(TestCase):
    def test_identical_vectors_score_one(self):
        self.assertAlmostEqual(_cosine_similarity([1, 2, 3], [1, 2, 3]), 1.0)

    def test_orthogonal_vectors_score_zero(self):
        self.assertAlmostEqual(_cosine_similarity([1, 0], [0, 1]), 0.0)

    def test_opposite_vectors_score_negative_one(self):
        self.assertAlmostEqual(_cosine_similarity([1, 2], [-1, -2]), -1.0)

    def test_zero_vector_scores_zero_instead_of_dividing_by_zero(self):
        self.assertEqual(_cosine_similarity([0, 0], [1, 2]), 0.0)


class RetrieveRelevantChunksTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user('owner', password='pw12345678')
        self.other = User.objects.create_user('other', password='pw12345678')

    def _make_completed_document(self, owner, title):
        return Document.objects.create(owner=owner, title=title, file_type='txt', status='completed')

    @mock.patch('todos.rag.embed_texts')
    def test_ranks_by_similarity_highest_first(self, mock_embed_texts):
        document = self._make_completed_document(self.owner, 'notes.txt')
        close_chunk = DocumentChunk.objects.create(document=document, chunk_index=0, text='close', embedding=[1, 0])
        far_chunk = DocumentChunk.objects.create(document=document, chunk_index=1, text='far', embedding=[0, 1])
        mock_embed_texts.return_value = [[1, 0]]

        results = retrieve_relevant_chunks(self.owner, 'query')

        self.assertEqual([chunk for chunk, _score in results], [close_chunk])
        self.assertNotIn(far_chunk, [chunk for chunk, _score in results])

    @mock.patch('todos.rag.embed_texts')
    def test_only_returns_the_requesting_users_chunks(self, mock_embed_texts):
        own_document = self._make_completed_document(self.owner, 'mine.txt')
        DocumentChunk.objects.create(document=own_document, chunk_index=0, text='mine', embedding=[1, 0])
        other_document = self._make_completed_document(self.other, 'theirs.txt')
        DocumentChunk.objects.create(document=other_document, chunk_index=0, text='theirs', embedding=[1, 0])
        mock_embed_texts.return_value = [[1, 0]]

        results = retrieve_relevant_chunks(self.owner, 'query')

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0].document, own_document)

    @mock.patch('todos.rag.embed_texts')
    def test_no_documents_skips_the_embedding_call_entirely(self, mock_embed_texts):
        results = retrieve_relevant_chunks(self.owner, 'query')

        self.assertEqual(results, [])
        mock_embed_texts.assert_not_called()

    @mock.patch('todos.rag.embed_texts')
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
