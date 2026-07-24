"""
Root URL configuration for the project.

This file only does routing at the project level — it delegates everything
app-specific to each app's own `urls.py` via `include()`. See config/README.md
for why the project/app split exists.
"""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('api/', include('todos.api.urls')),
    path('', include('todos.urls')),
]
