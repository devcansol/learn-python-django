# `config/` — the Django project

**Start here.** This is the "project" in Django's project/app split: it holds settings and the
root URL router, but no models or views of its own. Everything domain-specific lives in the
`accounts/` and `todos/` **apps** next to it.

## Concepts demonstrated

### Project vs. app
A Django **project** is the whole site — one settings file, one root URLconf. An **app** is a
self-contained bundle of models/views/templates for one piece of functionality (`accounts`,
`todos`). A project can contain many apps, and a well-designed app can be dropped into a
different project. This repo's project is called `config` (some tutorials call it after the
site's name, e.g. `mysite`) to keep that distinction visible in the folder name.

### `settings.py`
Central configuration, read once at process start:
- `INSTALLED_APPS` — every app (ours and Django's built-ins) must be listed here before its
  models, template tags, or admin registrations are picked up.
- `MIDDLEWARE` — a pipeline every request/response passes through (sessions, auth, CSRF, ...).
- `DATABASES` — SQLite here, zero setup required. Swap the `ENGINE`/credentials to point at
  Postgres/MySQL without touching any app code.
- `TEMPLATES['DIRS']` — points at the project-level `templates/` folder so apps can share a
  `base.html` rather than each duplicating page chrome.
- `LOGIN_URL` / `LOGIN_REDIRECT_URL` — read by `@login_required` and `LoginRequiredMixin`
  (used throughout `todos/views.py`) to know where to send anonymous users and where to send
  them after they log in.
- `REST_FRAMEWORK` — global defaults for the API in `todos/api/`.

### `urls.py` (root URLconf)
Django resolves an incoming path by walking `urlpatterns` top to bottom. Rather than listing
every page here, the root file `include()`s each app's own `urls.py` — the project says "any
path under `/accounts/` belongs to the accounts app" and stops looking further once it hands
off. This keeps routing decisions next to the views that implement them.

### `wsgi.py` / `asgi.py`
Entry points a production server (gunicorn, uvicorn, etc.) uses to talk to the Django
application. `manage.py runserver` uses neither directly — it has its own lightweight dev
server — but production deployments point at one of these.

## Where to go next

Read `accounts/README.md`, then `todos/README.md`, then `todos/api/README.md` — see the root
`README.md`'s "Learning path" section for the suggested order.
