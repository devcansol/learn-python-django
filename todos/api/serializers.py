from rest_framework import serializers

from todos.models import ChatMessage, Project, Task


class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = ['id', 'project', 'title', 'description', 'is_done', 'due_date', 'completed_at']
        read_only_fields = ['completed_at']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Restrict which projects a task can be assigned to, to ones the
        # requesting user owns — otherwise any authenticated user could file
        # a task under someone else's project by guessing its id.
        request = self.context.get('request')
        if request is not None:
            self.fields['project'].queryset = Project.objects.filter(owner=request.user)


class ProjectSerializer(serializers.ModelSerializer):
    tasks = TaskSerializer(many=True, read_only=True)

    class Meta:
        model = Project
        fields = ['id', 'owner', 'name', 'description', 'created_at', 'tasks']
        read_only_fields = ['owner']


class GenerateDescriptionSerializer(serializers.Serializer):
    """Input for the "Generate with AI" description helper — not tied to a
    model, just validates what todos/ai.py needs."""

    kind = serializers.ChoiceField(choices=['project', 'task'])
    subject = serializers.CharField(max_length=200)
    hint = serializers.CharField(max_length=300, required=False, allow_blank=True)
    parent_context = serializers.CharField(max_length=200, required=False, allow_blank=True)


class ChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = ['id', 'role', 'content', 'created_at']


class ChatSendSerializer(serializers.Serializer):
    """Input for posting a new chat message — not tied to a model, just
    validates what todos/ai.py's answer_question needs."""

    message = serializers.CharField(max_length=2000)
