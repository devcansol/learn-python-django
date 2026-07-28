from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from todos.ai import AIServiceError, generate_description
from todos.models import Project, Task

from .serializers import GenerateDescriptionSerializer, ProjectSerializer, TaskSerializer


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
