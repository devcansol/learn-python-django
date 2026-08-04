from django.http import StreamingHttpResponse
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from todos.ai import AIServiceError, generate_description, stream_answer
from todos.models import ChatMessage, Project, Task

from .serializers import (
    ChatMessageSerializer,
    ChatSendSerializer,
    GenerateDescriptionSerializer,
    ProjectSerializer,
    TaskSerializer,
)

HISTORY_LIMIT = 20   # messages of model context per request, not a display cap
DISPLAY_LIMIT = 200  # oldest-first cap on what GET returns, so the transcript can't grow unbounded


def _build_task_context(user):
    projects = Project.objects.filter(owner=user).prefetch_related('tasks')
    if not projects:
        return 'The user has no projects or tasks yet.'
    lines = []
    for project in projects:
        lines.append(f'Project: {project.name}' + (f' — {project.description}' if project.description else ''))
        for task in project.tasks.all():
            status = 'done' if task.is_done else 'open'
            due = f', due {task.due_date}' if task.due_date else ''
            lines.append(f'  - [{status}] {task.title}{due}')
    return '\n'.join(lines)


class ProjectViewSet(viewsets.ModelViewSet):
    """ModelViewSet bundles list/retrieve/create/update/destroy into one
    class, wired up entirely by the router in urls.py — no per-action
    url_patterns to write, unlike the FBV/CBV pattern in todos/views.py."""

    serializer_class = ProjectSerializer

    def get_queryset(self):
        return Project.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class TaskViewSet(viewsets.ModelViewSet):
    serializer_class = TaskSerializer

    def get_queryset(self):
        return Task.objects.filter(project__owner=self.request.user)


class GenerateDescriptionView(APIView):
    """Backs the "Generate with AI" button on the project/task forms —
    keeps the OpenRouter API key server-side (see todos/ai.py)."""

    def post(self, request):
        serializer = GenerateDescriptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            description = generate_description(
                subject=serializer.validated_data['subject'],
                hint=serializer.validated_data.get('hint', ''),
                parent_context=serializer.validated_data.get('parent_context', ''),
            )
        except AIServiceError as exc:
            status_code = 429 if 'rate-limited' in str(exc) else 502
            return Response({'error': str(exc)}, status=status_code)

        return Response({'description': description})


class ChatView(APIView):
    """Backs the floating chat widget — history persisted per-user in
    ChatMessage, answers grounded in the user's own Project/Task data."""

    def get(self, request):
        messages = list(ChatMessage.objects.filter(owner=request.user).order_by('-created_at')[:DISPLAY_LIMIT])[::-1]
        return Response(ChatMessageSerializer(messages, many=True).data)

    def post(self, request):
        serializer = ChatSendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        text = serializer.validated_data['message']

        history = list(ChatMessage.objects.filter(owner=request.user).order_by('-created_at')[:HISTORY_LIMIT])[::-1]
        ChatMessage.objects.create(owner=request.user, role='user', content=text)

        try:
            chunks = stream_answer(text, history=history, context=_build_task_context(request.user))
        except AIServiceError as exc:
            status_code = 429 if 'rate-limited' in str(exc) else 502
            return Response({'error': str(exc)}, status=status_code)

        def body():
            collected = []
            for chunk in chunks:
                collected.append(chunk)
                yield chunk.encode('utf-8')
            if collected:
                ChatMessage.objects.create(owner=request.user, role='assistant', content=''.join(collected))

        return StreamingHttpResponse(body(), content_type='text/plain; charset=utf-8')
