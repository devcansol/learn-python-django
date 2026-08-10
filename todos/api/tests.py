import shutil
import tempfile
from unittest import mock

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from todos.ai import AIServiceError
from todos.models import ChatMessage, Document, DocumentChunk, Project, Task


class ProjectApiTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user('owner', password='pw12345678')
        self.other = User.objects.create_user('other', password='pw12345678')
        self.project = Project.objects.create(owner=self.owner, name='Home')

    def test_anonymous_request_is_rejected(self):
        response = self.client.get(reverse('project-list'))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_only_returns_own_projects(self):
        Project.objects.create(owner=self.other, name='Not yours')
        self.client.force_authenticate(self.owner)

        response = self.client.get(reverse('project-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [p['name'] for p in response.data]
        self.assertEqual(names, ['Home'])

    def test_create_assigns_current_user_as_owner(self):
        self.client.force_authenticate(self.owner)

        response = self.client.post(reverse('project-list'), {'name': 'Work'})

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Project.objects.get(name='Work').owner, self.owner)


class TaskApiTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user('owner', password='pw12345678')
        self.other = User.objects.create_user('other', password='pw12345678')
        self.project = Project.objects.create(owner=self.owner, name='Home')
        self.other_project = Project.objects.create(owner=self.other, name='Not yours')

    def test_cannot_create_task_under_another_users_project(self):
        self.client.force_authenticate(self.owner)

        response = self.client.post(reverse('task-list'), {
            'project': self.other_project.pk,
            'title': 'Sneaky task',
        })

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_completed_at_is_read_only_on_the_wire(self):
        self.client.force_authenticate(self.owner)

        response = self.client.post(reverse('task-list'), {
            'project': self.project.pk,
            'title': 'Buy milk',
            'completed_at': '2020-01-01T00:00:00Z',
        })

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        task = Task.objects.get(pk=response.data['id'])
        self.assertIsNone(task.completed_at)


class DocumentApiTests(APITestCase):
    """Uses a throwaway MEDIA_ROOT so uploaded test files land in a temp
    dir instead of the real media/ folder."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._media_root = tempfile.mkdtemp()
        cls._media_override = override_settings(MEDIA_ROOT=cls._media_root)
        cls._media_override.enable()

    @classmethod
    def tearDownClass(cls):
        cls._media_override.disable()
        shutil.rmtree(cls._media_root, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.owner = User.objects.create_user('owner', password='pw12345678')
        self.other = User.objects.create_user('other', password='pw12345678')

    def test_anonymous_request_is_rejected(self):
        response = self.client.get(reverse('document-list'))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @mock.patch('todos.rag.embed_texts')
    def test_upload_txt_file_is_indexed_synchronously(self, mock_embed_texts):
        # Short enough to become a single chunk (well under CHUNK_SIZE_CHARS).
        mock_embed_texts.return_value = [[0.1, 0.2]]
        self.client.force_authenticate(self.owner)
        upload = SimpleUploadedFile('notes.txt', b'Paragraph one.\n\nParagraph two.')

        response = self.client.post(reverse('document-list'), {'file': upload}, format='multipart')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], 'completed')
        document = Document.objects.get(pk=response.data['id'])
        self.assertEqual(document.owner, self.owner)
        self.assertEqual(document.chunk_count, 1)
        self.assertEqual(DocumentChunk.objects.filter(document=document).count(), 1)

    def test_upload_rejects_unsupported_extension(self):
        self.client.force_authenticate(self.owner)
        upload = SimpleUploadedFile('malware.exe', b'binary junk')

        response = self.client.post(reverse('document-list'), {'file': upload}, format='multipart')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @mock.patch('todos.api.serializers.MAX_UPLOAD_SIZE', 10)
    def test_upload_rejects_oversized_file(self):
        self.client.force_authenticate(self.owner)
        upload = SimpleUploadedFile('notes.txt', b'this file is definitely larger than ten bytes')

        response = self.client.post(reverse('document-list'), {'file': upload}, format='multipart')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @mock.patch('todos.rag.embed_texts', side_effect=AIServiceError('The AI service returned an error while embedding text.'))
    def test_upload_marks_document_failed_instead_of_500_on_embedding_error(self, mock_embed_texts):
        self.client.force_authenticate(self.owner)
        upload = SimpleUploadedFile('notes.txt', b'some content to embed')

        response = self.client.post(reverse('document-list'), {'file': upload}, format='multipart')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], 'failed')
        self.assertTrue(response.data['error_message'])

    def test_list_only_returns_own_documents(self):
        Document.objects.create(owner=self.owner, title='mine.txt', file_type='txt', status='completed')
        Document.objects.create(owner=self.other, title='theirs.txt', file_type='txt', status='completed')
        self.client.force_authenticate(self.owner)

        response = self.client.get(reverse('document-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [doc['title'] for doc in response.data]
        self.assertEqual(titles, ['mine.txt'])

    def test_delete_removes_document_chunks_and_file(self):
        document = Document.objects.create(
            owner=self.owner,
            title='notes.txt',
            file=SimpleUploadedFile('notes.txt', b'hello world'),
            file_type='txt',
            status='completed',
        )
        DocumentChunk.objects.create(document=document, chunk_index=0, text='hello world', embedding=[0.1])
        file_name = document.file.name
        storage = document.file.storage
        self.client.force_authenticate(self.owner)

        response = self.client.delete(reverse('document-detail', kwargs={'pk': document.pk}))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Document.objects.filter(pk=document.pk).exists())
        self.assertEqual(DocumentChunk.objects.count(), 0)
        self.assertFalse(storage.exists(file_name))

    def test_cannot_delete_another_users_document(self):
        document = Document.objects.create(owner=self.other, title='theirs.txt', file_type='txt', status='completed')
        self.client.force_authenticate(self.owner)

        response = self.client.delete(reverse('document-detail', kwargs={'pk': document.pk}))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Document.objects.filter(pk=document.pk).exists())


class ChatViewTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user('owner', password='pw12345678')

    @mock.patch('todos.api.views.stream_answer')
    @mock.patch('todos.api.views.build_retrieved_context')
    @mock.patch('todos.api.views.retrieve_relevant_chunks')
    def test_retrieved_context_reaches_stream_answer(self, mock_retrieve, mock_build_context, mock_stream_answer):
        mock_retrieve.return_value = ['some-scored-chunk']
        mock_build_context.return_value = '[Source: notes.txt, chunk 0]\nsome retrieved text'
        mock_stream_answer.return_value = iter(['Hello!'])
        self.client.force_authenticate(self.owner)

        response = self.client.post(reverse('ai-chat'), {'message': 'What does notes.txt say?'})
        b''.join(response.streaming_content)

        mock_retrieve.assert_called_once_with(self.owner, 'What does notes.txt say?')
        mock_stream_answer.assert_called_once()
        self.assertEqual(
            mock_stream_answer.call_args.kwargs['retrieved_context'],
            '[Source: notes.txt, chunk 0]\nsome retrieved text',
        )

    @mock.patch('todos.api.views.stream_answer')
    @mock.patch('todos.api.views.retrieve_relevant_chunks', side_effect=AIServiceError('rate-limited'))
    def test_retrieval_failure_falls_back_to_task_context_only(self, mock_retrieve, mock_stream_answer):
        mock_stream_answer.return_value = iter(['Hello!'])
        self.client.force_authenticate(self.owner)

        response = self.client.post(reverse('ai-chat'), {'message': 'Anything in my docs?'})
        b''.join(response.streaming_content)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(mock_stream_answer.call_args.kwargs['retrieved_context'], '')
        self.assertTrue(ChatMessage.objects.filter(owner=self.owner, role='assistant').exists())
