from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, render
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from .forms import ProjectForm, TaskForm
from .mixins import OwnerQuerySetMixin
from .models import Project, Task


@login_required
def dashboard(request):
    """A plain function-based view: fetch what the template needs, render it.
    No queryset/template-name conventions to learn — contrast with the
    class-based views below, which trade this explicitness for less
    boilerplate once a view is "just" list/create/update/delete."""
    projects = request.user.projects.all()
    upcoming_tasks = (
        Task.objects.filter(project__owner=request.user, is_done=False)
        .select_related('project')
        .order_by('due_date')[:5]
    )

    # These print() calls show up in the terminal running `manage.py runserver`,
    # not in the browser — this code runs on the server, before any HTML is
    # sent back. Compare with the console.log() calls in dashboard.html, which
    # run on the student's machine once the page arrives.
    print(f'[server console] dashboard view: request from {request.user}')
    print(f'[server console] dashboard view: {projects.count()} project(s) loaded')
    print(f'[server console] dashboard view: {len(upcoming_tasks)} upcoming task(s) loaded')

    return render(request, 'todos/dashboard.html', {
        'projects': projects,
        'upcoming_tasks': upcoming_tasks,
    })


class ProjectListView(OwnerQuerySetMixin, ListView):
    model = Project
    context_object_name = 'projects'


class ProjectDetailView(OwnerQuerySetMixin, DetailView):
    model = Project
    context_object_name = 'project'


class ProjectCreateView(LoginRequiredMixin, CreateView):
    model = Project
    form_class = ProjectForm

    def form_valid(self, form):
        # CreateView has no "owner" concept of its own — we assign it here,
        # before the object is saved, rather than trusting a hidden form field
        # (which a client could tamper with).
        form.instance.owner = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('todos:project-detail', kwargs={'pk': self.object.pk})


class ProjectUpdateView(OwnerQuerySetMixin, UpdateView):
    model = Project
    form_class = ProjectForm

    def get_success_url(self):
        return reverse('todos:project-detail', kwargs={'pk': self.object.pk})


class ProjectDeleteView(OwnerQuerySetMixin, DeleteView):
    model = Project
    success_url = reverse_lazy('todos:project-list')


class TaskCreateView(LoginRequiredMixin, CreateView):
    model = Task
    form_class = TaskForm

    def get_project(self):
        # 404s for both "no such project" and "not yours" alike — same
        # information-hiding reasoning as OwnerQuerySetMixin.
        return get_object_or_404(Project, pk=self.kwargs['project_pk'], owner=self.request.user)

    def form_valid(self, form):
        form.instance.project = self.get_project()
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        return super().get_context_data(project=self.get_project(), **kwargs)

    def get_success_url(self):
        return reverse('todos:project-detail', kwargs={'pk': self.object.project_id})


class TaskUpdateView(OwnerQuerySetMixin, UpdateView):
    model = Task
    form_class = TaskForm
    owner_lookup = 'project__owner'

    def get_success_url(self):
        return reverse('todos:project-detail', kwargs={'pk': self.object.project_id})


class TaskDeleteView(OwnerQuerySetMixin, DeleteView):
    model = Task
    owner_lookup = 'project__owner'

    def get_success_url(self):
        return reverse('todos:project-detail', kwargs={'pk': self.object.project_id})
