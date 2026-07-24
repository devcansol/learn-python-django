from rest_framework import viewsets

from todos.models import Project, Task

from .serializers import ProjectSerializer, TaskSerializer


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
