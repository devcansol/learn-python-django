from django.contrib.auth import login
from django.urls import reverse_lazy
from django.views.generic import CreateView

from .forms import SignUpForm


class SignUpView(CreateView):
    """CreateView already knows how to render a form and save() a valid one;
    we override form_valid() to also log the new user straight in, since
    Django won't do that for you automatically after CreateView.save()."""

    form_class = SignUpForm
    template_name = 'registration/signup.html'
    success_url = reverse_lazy('todos:dashboard')

    def form_valid(self, form):
        response = super().form_valid(form)
        login(self.request, self.object)
        return response
