from rest_framework import serializers

from todos.models import ChatMessage, Document, Project, Task
from todos.rag import ALLOWED_EXTENSIONS, MAX_UPLOAD_SIZE


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
    validates what todos/ai.py's stream_answer needs."""

    message = serializers.CharField(max_length=2000)


class DocumentSerializer(serializers.ModelSerializer):
    """Upload/list a Document for the chat widget's RAG knowledge base —
    see todos/rag.py:index_document. `file` is write-only: the uploaded
    file is never echoed back or exposed by URL (see todos/rag.py's
    module docstring for why)."""

    file = serializers.FileField(write_only=True)
    title = serializers.CharField(max_length=255, required=False, allow_blank=True)

    class Meta:
        model = Document
        fields = ['id', 'title', 'file', 'file_type', 'status', 'char_count', 'chunk_count', 'error_message', 'created_at']
        read_only_fields = ['file_type', 'status', 'char_count', 'chunk_count', 'error_message', 'created_at']

    def validate_file(self, value):
        extension = value.name.rsplit('.', 1)[-1].lower() if '.' in value.name else ''
        if extension not in ALLOWED_EXTENSIONS:
            raise serializers.ValidationError('Only .txt, .md, and .pdf files are supported.')
        if value.size > MAX_UPLOAD_SIZE:
            raise serializers.ValidationError(f'File is too large — max {MAX_UPLOAD_SIZE // (1024 * 1024)}MB.')
        return value
