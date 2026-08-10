from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import ChatView, DocumentViewSet, GenerateDescriptionView, ProjectViewSet, TaskViewSet

# DefaultRouter inspects each ViewSet's actions and generates the matching
# URL patterns (list/detail/etc.) plus a browsable API root — the DRF
# counterpart to hand-writing every path() in todos/urls.py.
router = DefaultRouter()
router.register('projects', ProjectViewSet, basename='project')
router.register('tasks', TaskViewSet, basename='task')
router.register('documents', DocumentViewSet, basename='document')

urlpatterns = router.urls + [
    path('ai/generate-description/', GenerateDescriptionView.as_view(), name='generate-description'),
    path('ai/chat/', ChatView.as_view(), name='ai-chat'),
]
