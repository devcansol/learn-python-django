# `accounts/` — authentication

Everything needed to sign up, log in, and log out, built almost entirely from pieces Django
already ships. The lesson here is how *little* code auth normally requires.

## Concepts demonstrated

### Django's built-in `User` model
`django.contrib.auth.models.User` gives you username, password (hashed with PBKDF2 by
default), email, and staff/superuser flags for free. We don't subclass or replace it — see
the comment in `models.py`. `todos/models.py`'s `Project.owner` points straight at it.

### Built-in auth views
`accounts/urls.py` wires up `django.contrib.auth.views.LoginView` and `LogoutView` directly —
we supply only a template for `LoginView` (`templates/registration/login.html`); the view
itself handles credential checking, session creation, and the `?next=` redirect chain. This is
the "don't write what Django already gives you" half of the lesson — contrast with `SignUpView`
below, which Django has no built-in for.

### `ModelForm` via `UserCreationForm`
`accounts/forms.py`'s `SignUpForm` subclasses `UserCreationForm`, which already validates that
two password fields match and calls `set_password()` (never storing plaintext) on `save()`. We
only add an `email` field and list it in `Meta.fields`.

### Class-based view: `CreateView`
`accounts/views.py`'s `SignUpView` is a `CreateView` — given `form_class` and `template_name`,
it handles GET (render blank form), POST (validate + save), and redirecting to `success_url`.
We override `form_valid()` for one thing CreateView doesn't do by default: logging the new user
in immediately after signup.

### `login_required` / `LOGIN_URL`
This app doesn't gate anything itself, but it's the *destination* other apps' `login_required`
checks redirect to. See `config/settings.py`'s `LOGIN_URL = 'accounts:login'` and how
`todos/views.py`'s dashboard uses `@login_required`.

### Password reset — four built-in views, no custom logic
`accounts/urls.py` wires up `PasswordResetView` -> `PasswordResetDoneView` ->
`PasswordResetConfirmView` -> `PasswordResetCompleteView`. Django handles everything: generating
a signed, single-use, time-limited token (`PASSWORD_RESET_TIMEOUT`, default 3 days), emailing it,
validating it, and setting the new password. We only supply templates plus the email body/subject
templates. One gotcha worth noting: `PasswordResetView`/`PasswordResetConfirmView` default
`success_url` to *unnamespaced* view names (`reverse_lazy("password_reset_done")`), which 404s
under our `app_name = "accounts"` — so `urls.py` passes `success_url=reverse_lazy("accounts:...")`
explicitly via `.as_view()`, the same pattern already used for `template_name`.

Since there's no real mail server here, `EMAIL_BACKEND` in `config/settings.py` is set to
Django's console backend — reset emails print to the terminal running `runserver` instead of
being sent anywhere.

## Try it

1. Visit `/accounts/signup/` — create a user, note you land on the dashboard already logged in.
2. Visit `/accounts/logout/` then hit the dashboard URL directly — you're bounced to
   `/accounts/login/?next=/...`.
3. Visit `/accounts/login/`, click "Forgot your password?", and submit the email you signed up
   with. Check the terminal running `runserver` — the reset email (with a clickable link) prints
   there via the console `EMAIL_BACKEND`. Open the link to set a new password.
4. `python manage.py test accounts` — covers the signup happy path, a validation failure
   (mismatched passwords), the anonymous-redirect behavior, and the password reset flow (email
   sent, unknown-email is indistinguishable from known, valid token succeeds, invalid token is
   rejected).
