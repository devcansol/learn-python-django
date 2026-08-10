import uuid

from django.conf import settings
from django.db import models


class Project(models.Model):
    """A container of tasks, owned by exactly one user."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='projects',
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class Task(models.Model):
    """A single to-do item that belongs to a Project."""

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='tasks')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    is_done = models.BooleanField(default=False)
    due_date = models.DateField(null=True, blank=True)
    # Set/cleared automatically by todos/signals.py when is_done changes —
    # never assigned directly by a view or form.
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['is_done', '-created_at']

    def __str__(self):
        return self.title


class ChatMessage(models.Model):
    """One turn in a user's AI chat history — see todos/ai.py:stream_answer."""

    ROLE_CHOICES = [('user', 'User'), ('assistant', 'Assistant')]

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='chat_messages',
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'{self.role}: {self.content[:50]}'


def document_upload_path(instance, filename):
    # Namespaced by owner id + a random suffix so two users' same-named
    # files never collide on disk and a guessed path can't leak another
    # user's filename.
    return f'documents/user_{instance.owner_id}/{uuid.uuid4().hex}_{filename}'


class Document(models.Model):
    """A file the user uploaded to their personal RAG knowledge base — see
    todos/rag.py for how it gets chunked/embedded and todos/ai.py's
    stream_answer for how retrieved chunks get grounded into a chat reply.

    Forms a global per-user knowledge base (like ChatMessage), not scoped
    to a single Project."""

    FILE_TYPE_CHOICES = [('txt', 'Text'), ('md', 'Markdown'), ('pdf', 'PDF')]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='documents',
    )
    title = models.CharField(max_length=255, blank=True)
    file = models.FileField(upload_to=document_upload_path)
    file_type = models.CharField(max_length=10, choices=FILE_TYPE_CHOICES)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='pending')
    char_count = models.PositiveIntegerField(default=0)
    chunk_count = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class DocumentChunk(models.Model):
    """One retrieval-sized slice of a Document's extracted text, plus the
    embedding vector used for cosine-similarity search — see
    todos/rag.py:chunk_text / retrieve_relevant_chunks."""

    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='chunks')
    chunk_index = models.PositiveIntegerField()
    text = models.TextField()
    # Raw list[float] (1536 numbers for text-embedding-3-small). SQLite's
    # JSON1 support makes JSONField work here with no extra dependency.
    embedding = models.JSONField()

    class Meta:
        ordering = ['document', 'chunk_index']
        constraints = [
            models.UniqueConstraint(fields=['document', 'chunk_index'], name='unique_chunk_index_per_document'),
        ]

    def __str__(self):
        return f'{self.document.title} [{self.chunk_index}]'
