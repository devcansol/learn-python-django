# `todos/` — the core domain

`Project` and `Task` are the heart of the app. This is where most of Django's day-to-day
building blocks show up: models, migrations, both flavors of view, forms, signals, and the
admin.

## Concepts demonstrated

### Models & migrations (`models.py`)
`Project` and `Task` are plain `models.Model` subclasses; `Task.project` is a `ForeignKey`
to `Project` with `related_name='tasks'`, so `some_project.tasks.all()` works without a
separate query helper. Every field change here needs a matching **migration**
(`python manage.py makemigrations todos`) — the migration is the versioned, replayable record
of how the database schema got from empty to its current shape; Django never inspects your
models to guess the schema at runtime.

### Function-based view vs. class-based view
`views.py::dashboard` is a plain function: fetch what the template needs, `render()` it. No
naming conventions to learn, but every branch (auth check, queries, context) is spelled out
by hand.

The `Project*`/`Task*` views below it are **class-based views** (`ListView`, `DetailView`,
`CreateView`, `UpdateView`, `DeleteView`) — each already knows how to do one CRUD operation
given a `model`/`form_class`/(optional) `template_name`, and you override only the piece that
differs (e.g. `form_valid()` to stamp the owner). Same functionality, less repetition, at the
cost of needing to know the base class's method-resolution order to customize it.

### `ModelForm` (`forms.py`)
`ProjectForm`/`TaskForm` derive their fields straight from the model, so validation (required
fields, max lengths, etc.) is defined once, on the model, and reused everywhere the model is
edited. Note `TaskForm.Meta.fields` excludes `completed_at` on purpose — see signals below.

### Authorization: `mixins.py`
Django's `LoginRequiredMixin` only checks *is somebody logged in*. Whether *this* user may see
*this* project is a separate, app-specific question — `OwnerQuerySetMixin` answers it by
filtering the queryset itself, so an unauthorized request 404s (object not found) rather than
403s (object exists, you can't have it) or leaking data by accident. `TaskCreateView` needs the
same check in a different shape (there's no existing Task to filter yet), so it does the
equivalent with `get_object_or_404(Project, pk=..., owner=request.user)`.

### Signals (`signals.py` + `apps.py`)
`stamp_completed_at` connects to `Task`'s `pre_save` signal and keeps `completed_at` in sync
with `is_done`, no matter whether the change came from a view, the admin, or a shell script.
The connection is registered in `TodosConfig.ready()` (`apps.py`) — Django calls `ready()` once
the app registry is fully loaded, which is the documented place signal handlers are supposed to
be imported from.

### Admin customization (`admin.py`)
Beyond plain `admin.site.register(Model)`, `ProjectAdmin`/`TaskAdmin` add `list_display`,
`list_filter`, and `search_fields` for a usable change-list, and `TaskInline` lets you edit a
project's tasks on the same admin page as the project.

## Try it

1. Log in, create a project, add a couple of tasks, toggle one done — check `/admin/` and see
   `completed_at` populate on its own.
2. Log in as a second user and try to open the first user's project detail URL directly — 404.
3. `python manage.py test todos` — model behavior, the signal, and the ownership checks above.

## Next: `todos/api/`

Same `Project`/`Task` models, exposed as a small REST API — see `todos/api/README.md`.
