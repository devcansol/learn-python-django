from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class SignUpTests(TestCase):
    def test_signup_creates_user_and_logs_in(self):
        response = self.client.post(reverse('accounts:signup'), {
            'username': 'alice',
            'email': 'alice@example.com',
            'password1': 'a-very-unguessable-pw9',
            'password2': 'a-very-unguessable-pw9',
        })

        self.assertTrue(User.objects.filter(username='alice').exists())
        # SignUpView.form_valid() logs the new user in, so the dashboard
        # (a @login_required view) should now be reachable without a separate login.
        self.assertRedirects(response, reverse('todos:dashboard'))

    def test_signup_rejects_mismatched_passwords(self):
        response = self.client.post(reverse('accounts:signup'), {
            'username': 'bob',
            'email': 'bob@example.com',
            'password1': 'a-very-unguessable-pw9',
            'password2': 'does-not-match',
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='bob').exists())


class LoginRequiredTests(TestCase):
    def test_dashboard_redirects_anonymous_user_to_login(self):
        response = self.client.get(reverse('todos:dashboard'))
        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={reverse('todos:dashboard')}",
        )
