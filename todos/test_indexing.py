import io
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase

from .indexing import _run_indexing, chunk_text, enqueue_indexing, extract_text
from .models import Document


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

        with mock.patch('todos.indexing.pypdf.PdfReader') as mock_reader:
            mock_reader.return_value.pages = [fake_page_1, fake_page_2]
            text = extract_text(io.BytesIO(b'%PDF-fake'), 'pdf')

        self.assertEqual(text, 'Page one.\n\nPage two.')

    def test_unsupported_file_type_raises(self):
        with self.assertRaises(ValueError):
            extract_text(io.BytesIO(b''), 'docx')


class EnqueueIndexingTests(TestCase):
    def test_enqueue_indexing_starts_a_daemon_thread(self):
        with mock.patch('todos.indexing.threading.Thread') as mock_thread_cls:
            enqueue_indexing(42)

        mock_thread_cls.assert_called_once_with(target=_run_indexing, args=(42,), daemon=True)
        mock_thread_cls.return_value.start.assert_called_once()

    @mock.patch('todos.indexing.connection')
    @mock.patch('todos.indexing.index_document')
    def test_run_indexing_fetches_by_pk_and_closes_the_connection(self, mock_index_document, mock_connection):
        owner = User.objects.create_user('owner', password='pw12345678')
        document = Document.objects.create(owner=owner, title='notes.txt', file_type='txt', status='pending')

        _run_indexing(document.pk)

        mock_index_document.assert_called_once()
        (called_document,), _kwargs = mock_index_document.call_args
        self.assertEqual(called_document.pk, document.pk)
        mock_connection.close.assert_called_once()
