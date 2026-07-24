from django import forms

from .models import Project, Task


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ['name', 'description']


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        # Deliberately excludes `completed_at`: that field is signal-managed
        # (see signals.py) and should never be settable through a form.
        fields = ['title', 'description', 'due_date', 'is_done']
        widgets = {
            'due_date': forms.DateInput(attrs={'type': 'date'}),
        }
