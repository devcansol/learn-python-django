from django.urls import path

from . import views

app_name = 'todos'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('documents/', views.documents, name='documents'),
    path('projects/', views.ProjectListView.as_view(), name='project-list'),
    path('projects/new/', views.ProjectCreateView.as_view(), name='project-create'),
    path('projects/<int:pk>/', views.ProjectDetailView.as_view(), name='project-detail'),
    path('projects/<int:pk>/edit/', views.ProjectUpdateView.as_view(), name='project-update'),
    path('projects/<int:pk>/delete/', views.ProjectDeleteView.as_view(), name='project-delete'),
    path('projects/<int:project_pk>/tasks/new/', views.TaskCreateView.as_view(), name='task-create'),
    path('tasks/<int:pk>/edit/', views.TaskUpdateView.as_view(), name='task-update'),
    path('tasks/<int:pk>/delete/', views.TaskDeleteView.as_view(), name='task-delete'),
]
