from django.apps import AppConfig


class TodosConfig(AppConfig):
    name = 'todos'

    def ready(self):
        # Importing registers the @receiver below via Django's signal
        # dispatcher; it must happen here (not in models.py) to avoid
        # running signal registration before the app registry is ready.
        from . import signals  # noqa: F401
