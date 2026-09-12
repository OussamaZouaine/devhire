from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.urls import reverse_lazy
from django.views.generic import CreateView, TemplateView, UpdateView

from .forms import CandidateProfileForm, CandidateSignUpForm, RecruiterSignUpForm
from .mixins import CandidateRequiredMixin
from .models import CandidateProfile


class SignUpChoiceView(TemplateView):
    template_name = "accounts/signup_choice.html"


class CandidateSignUpView(CreateView):
    form_class = CandidateSignUpForm
    template_name = "accounts/signup_candidate.html"
    success_url = reverse_lazy("accounts:login")


class RecruiterSignUpView(CreateView):
    form_class = RecruiterSignUpForm
    template_name = "accounts/signup_recruiter.html"
    success_url = reverse_lazy("accounts:login")


class LoginView(auth_views.LoginView):
    template_name = "accounts/login.html"

    def get_success_url(self) -> str:
        user = self.request.user
        if user.role == "recruiter":
            return reverse_lazy("jobs:recruiter_dashboard")
        return reverse_lazy("core:candidate_dashboard")


class LogoutView(auth_views.LogoutView):
    next_page = reverse_lazy("core:home")


class CandidateProfileUpdateView(CandidateRequiredMixin, UpdateView):
    model = CandidateProfile
    form_class = CandidateProfileForm
    template_name = "accounts/candidate_profile_form.html"
    success_url = reverse_lazy("core:candidate_dashboard")

    def get_object(self, queryset=None):
        return self.request.user.get_candidate_profile()

    def form_valid(self, form):
        messages.success(self.request, "Votre profil a été mis à jour avec succès.")
        return super().form_valid(form)
