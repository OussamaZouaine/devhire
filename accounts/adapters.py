from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.urls import reverse

from .models import User


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    """Users who sign up with Google become candidates (recruiters sign up with a company)."""

    def populate_user(self, request, sociallogin, data):
        user = super().populate_user(request, sociallogin, data)
        user.role = User.Role.CANDIDATE
        return user

    def get_connect_redirect_url(self, request, socialaccount):
        return reverse("core:candidate_dashboard")
