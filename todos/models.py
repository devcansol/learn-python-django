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
