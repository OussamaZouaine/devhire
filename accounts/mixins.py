from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.urls import reverse_lazy

from .models import User


class CandidateRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Restrict access to authenticated candidates."""

    login_url = reverse_lazy("accounts:login")

    def test_func(self) -> bool:
        return self.request.user.role == User.Role.CANDIDATE

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()
        raise PermissionDenied("Accès réservé aux candidats.")


class RecruiterRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Restrict access to authenticated recruiters."""

    login_url = reverse_lazy("accounts:login")

    def test_func(self) -> bool:
        return self.request.user.role == User.Role.RECRUITER

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()
        raise PermissionDenied("Accès réservé aux recruteurs.")
