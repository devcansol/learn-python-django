from django.contrib.auth import views as auth_views
from django.urls import path

from .views import SignUpView

app_name = 'accounts'

urlpatterns = [
    # Django ships working LoginView/LogoutView — we only supply templates
    # and tell them where to send the user afterwards (see settings.py).
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('signup/', SignUpView.as_view(), name='signup'),
]
