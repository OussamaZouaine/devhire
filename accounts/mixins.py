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

    def get_recruiter(self):
        return self.request.user.get_recruiter_profile()

    def get_company(self):
        return self.get_recruiter().company


class CompanyAdminRequiredMixin(RecruiterRequiredMixin):
    """Restrict access to the administrators of a company."""

    def test_func(self) -> bool:
        return super().test_func() and self.request.user.get_recruiter_profile().is_company_admin

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()
        raise PermissionDenied("Accès réservé aux administrateurs de l'entreprise.")
