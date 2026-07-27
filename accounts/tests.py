from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode


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


class PasswordResetTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='carol', email='carol@example.com', password='old-unguessable-pw9',
        )

    def test_request_form_emails_a_reset_link(self):
        response = self.client.post(reverse('accounts:password_reset'), {'email': 'carol@example.com'})

        self.assertRedirects(response, reverse('accounts:password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('accounts/password-reset/confirm/', mail.outbox[0].body)

    def test_request_form_with_unknown_email_sends_nothing_but_still_redirects(self):
        # Django deliberately doesn't reveal whether an email is registered —
        # the response looks identical either way.
        response = self.client.post(reverse('accounts:password_reset'), {'email': 'nobody@example.com'})

        self.assertRedirects(response, reverse('accounts:password_reset_done'))
        self.assertEqual(len(mail.outbox), 0)

    def test_valid_link_lets_user_set_a_new_password(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)

        # PasswordResetConfirmView swaps the token in the URL for a one-time
        # "set-password" session token on first GET, then re-renders the form
        # at a URL without the raw token — so we follow that redirect first.
        confirm_url = reverse('accounts:password_reset_confirm', kwargs={'uidb64': uid, 'token': token})
        response = self.client.get(confirm_url, follow=True)
        self.assertEqual(response.status_code, 200)

        response = self.client.post(response.request['PATH_INFO'], {
            'new_password1': 'brand-new-unguessable-pw9',
            'new_password2': 'brand-new-unguessable-pw9',
        })
        self.assertRedirects(response, reverse('accounts:password_reset_complete'))

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('brand-new-unguessable-pw9'))

    def test_invalid_token_rejects_reset(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        confirm_url = reverse('accounts:password_reset_confirm', kwargs={'uidb64': uid, 'token': 'bad-token'})

        response = self.client.get(confirm_url, follow=True)

        self.assertContains(response, 'invalid')
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('old-unguessable-pw9'))
