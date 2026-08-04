from django.contrib import admin

from .models import ChatMessage, Project, Task


class TaskInline(admin.TabularInline):
    """Lets you add/edit a project's tasks on the Project admin page itself,
    instead of navigating to the separate Task list."""
    model = Task
    extra = 1
    fields = ['title', 'is_done', 'due_date']


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'owner', 'created_at']
    list_filter = ['owner']
    search_fields = ['name']
    inlines = [TaskInline]


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ['title', 'project', 'is_done', 'due_date', 'completed_at']
    list_filter = ['is_done', 'project']
    search_fields = ['title']


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ['owner', 'role', 'created_at']
    list_filter = ['role', 'owner']
