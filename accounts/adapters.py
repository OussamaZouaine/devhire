from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.urls import reverse

from .models import Company, RecruiterProfile, User

# Role chosen on the sign-up pages before leaving for Google (see GoogleSignUpView).
SIGNUP_ROLE_SESSION_KEY = "google_signup_role"


def pending_signup_role(request) -> str:
    role = request.session.get(SIGNUP_ROLE_SESSION_KEY) if request is not None else None
    return role if role in User.Role.values else User.Role.CANDIDATE


class AccountAdapter(DefaultAccountAdapter):
    def get_login_redirect_url(self, request):
        """After a Google login, send each role to its own dashboard."""
        request.session.pop(SIGNUP_ROLE_SESSION_KEY, None)
        user = request.user
        if user.is_authenticated and user.role == User.Role.RECRUITER:
            return reverse("jobs:recruiter_dashboard")
        if user.is_authenticated and user.role == User.Role.CANDIDATE:
            return reverse("core:candidate_dashboard")
        return super().get_login_redirect_url(request)


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Google sign-up for both roles:
    - candidate: account created automatically (auto sign-up);
    - recruiter: a short form asks for the company name before the account is created.
    Without a role chosen beforehand (login page), new users become candidates.
    """

    def populate_user(self, request, sociallogin, data):
        user = super().populate_user(request, sociallogin, data)
        user.role = pending_signup_role(request)
        return user

    def is_auto_signup_allowed(self, request, sociallogin):
        if sociallogin.user.role == User.Role.RECRUITER:
            return False
        return super().is_auto_signup_allowed(request, sociallogin)

    def save_user(self, request, sociallogin, form=None):
        user = sociallogin.user
        if user.role == User.Role.RECRUITER:
            company_name = ""
            if form is not None:
                company_name = form.cleaned_data.get("company_name", "")
            company = Company.objects.create(name=company_name or f"Entreprise de {user.username}")
            # Read by the post_save signal so no placeholder company is created.
            user._pending_company = (company, RecruiterProfile.CompanyRole.ADMIN)
        user = super().save_user(request, sociallogin, form)
        if request is not None:
            request.session.pop(SIGNUP_ROLE_SESSION_KEY, None)
        return user

    def get_connect_redirect_url(self, request, socialaccount):
        return reverse("core:candidate_dashboard")
