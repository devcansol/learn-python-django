# `todos/api/` — a small REST API (Django REST Framework)

Same `Project`/`Task` models as the rest of `todos/`, exposed over HTTP as JSON instead of
HTML. This is the "intermediate" slice of the project — Django itself doesn't ship a REST
framework, so everything here comes from the third-party `djangorestframework` package
(`rest_framework` in `INSTALLED_APPS`).

## Concepts demonstrated

### Serializers (`serializers.py`)
A DRF `ModelSerializer` is the API analogue of a `ModelForm`: it derives fields from the model
and handles both directions — model instance → JSON (`.data`) and JSON → validated model fields
(`.is_valid()` / `.save()`). `TaskSerializer` overrides `__init__` to narrow the `project` field's
allowed choices to the requesting user's own projects — a common DRF pattern for scoping a
foreign key by the current user rather than exposing every project in the database.

### Viewsets (`views.py`)
A `ModelViewSet` bundles list/retrieve/create/update/destroy into a single class — the REST
counterpart to writing five separate CBVs. `get_queryset()` scopes every action to
`request.user` (never trust query params to say whose data to return); `perform_create()`
stamps the current user in as `owner` server-side, the same way `todos/views.py`'s
`ProjectCreateView.form_valid()` does for the HTML form.

### Routers (`urls.py`)
`DefaultRouter` inspects each `ModelViewSet` and generates the matching URL patterns
automatically (`GET/POST /projects/`, `GET/PUT/PATCH/DELETE /projects/{id}/`, ...), plus a
browsable API root at `/api/`. This trades explicit `path()` entries (see `todos/urls.py`) for
convention — worth noticing the tradeoff both ways.

### Permissions & authentication (`config/settings.py`)
`REST_FRAMEWORK['DEFAULT_PERMISSION_CLASSES']` requires `IsAuthenticated` project-wide, so an
anonymous request gets `403 Forbidden` before any view code runs.
`DEFAULT_AUTHENTICATION_CLASSES` uses `SessionAuthentication` — the same login session the
HTML site uses — so once you're logged in at `/accounts/login/`, `/api/` works from the same
browser tab.

## Try it

1. Log in via the site, then visit `/api/` in the same browser — DRF's browsable API lets you
   submit forms and see raw JSON responses without a separate HTTP client.
2. `curl` with a session cookie, or use `python manage.py test todos.api` — covers anonymous
   rejection, per-user scoping on list, owner assignment on create, cross-user task creation
   being rejected, and `completed_at` being ignored even if a client tries to set it directly.
