from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("inscription/", views.SignUpChoiceView.as_view(), name="signup_choice"),
    path(
        "inscription/candidat/",
        views.CandidateSignUpView.as_view(),
        name="signup_candidate",
    ),
    path(
        "inscription/recruteur/",
        views.RecruiterSignUpView.as_view(),
        name="signup_recruiter",
    ),
    path("connexion/", views.LoginView.as_view(), name="login"),
    path("deconnexion/", views.LogoutView.as_view(), name="logout"),
    path(
        "profil/candidat/",
        views.CandidateProfileUpdateView.as_view(),
        name="candidate_profile_update",
    ),
]
