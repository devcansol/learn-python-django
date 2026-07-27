from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from .views import SignUpView

app_name = 'accounts'

urlpatterns = [
    # Django ships working LoginView/LogoutView — we only supply templates
    # and tell them where to send the user afterwards (see settings.py).
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('signup/', SignUpView.as_view(), name='signup'),

    # Password reset is a 4-view chain, all built in: request form -> "email
    # sent" notice -> the emailed link (validates a signed token) -> "changed"
    # confirmation. We only supply templates; PASSWORD_RESET_TIMEOUT and
    # EMAIL_BACKEND live in settings.py.
    path(
        'password-reset/',
        auth_views.PasswordResetView.as_view(
            template_name='registration/password_reset_form.html',
            email_template_name='registration/password_reset_email.html',
            subject_template_name='registration/password_reset_subject.txt',
            # PasswordResetView.success_url defaults to reverse_lazy('password_reset_done'),
            # unnamespaced — it 404s under our app_name='accounts' unless overridden here.
            success_url=reverse_lazy('accounts:password_reset_done'),
        ),
        name='password_reset',
    ),
    path(
        'password-reset/done/',
        auth_views.PasswordResetDoneView.as_view(template_name='registration/password_reset_done.html'),
        name='password_reset_done',
    ),
    path(
        'password-reset/confirm/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='registration/password_reset_confirm.html',
            success_url=reverse_lazy('accounts:password_reset_complete'),
        ),
        name='password_reset_confirm',
    ),
    path(
        'password-reset/complete/',
        auth_views.PasswordResetCompleteView.as_view(template_name='registration/password_reset_complete.html'),
        name='password_reset_complete',
    ),
]
