# learn-python-django

A public repo to learn Python &amp; Django — core concepts, implementation and realtime use
cases — built as a working task/project manager. Every app in this repo demonstrates a
cluster of Django concepts and documents them in its own README, so you can read the code and
the "why" side by side.

## What's here

A small multi-user task manager:
- Sign up, log in, log out (`accounts/`)
- Create projects, add tasks to them, mark tasks done (`todos/`)
- The same data, available as a JSON REST API (`todos/api/`)
- Everything editable from the Django admin

Each user only ever sees their own projects and tasks.

## Setup

Requires Python 3.10+.

```bash
python3 -m venv venv
source venv/bin/activate        # venv\Scripts\activate on Windows
pip install -r requirements.txt

python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Then visit:
- `http://127.0.0.1:8000/` — the app (sign up, or log in if you already have an account)
- `http://127.0.0.1:8000/admin/` — the Django admin (log in with the superuser you just created)
- `http://127.0.0.1:8000/api/` — the browsable REST API (log in first at `/accounts/login/`)

Run the test suite with:

```bash
python manage.py test
```

## Learning path

Read in this order — each README builds on concepts from the ones before it:

1. **[`config/README.md`](config/README.md)** — the Django project itself: settings,
   `INSTALLED_APPS`, the root URLconf, and the project/app split.
2. **[`accounts/README.md`](accounts/README.md)** — Django's built-in auth system: the `User`
   model, built-in login/logout views, `UserCreationForm`, and `login_required`.
3. **[`todos/README.md`](todos/README.md)** — the core domain: models & migrations,
   function-based vs. class-based views, `ModelForm`, signals, authorization mixins, and admin
   customization.
4. **[`todos/api/README.md`](todos/api/README.md)** — the same domain exposed as a REST API
   with Django REST Framework: serializers, viewsets, routers, and permissions.

## Project layout

```
config/       Django project: settings, root URLs
accounts/     Auth: signup/login/logout
todos/        Core domain: Project & Task models, views, forms, admin, signals
todos/api/    REST API for the same models (Django REST Framework)
templates/    Shared HTML templates (base layout, auth pages, todos pages)
static/       CSS
```
