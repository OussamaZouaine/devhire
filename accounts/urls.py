from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

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
    # Password reset
    path(
        "mot-de-passe/oublie/",
        auth_views.PasswordResetView.as_view(
            template_name="accounts/password_reset_form.html",
            email_template_name="accounts/emails/password_reset_email.txt",
            subject_template_name="accounts/emails/password_reset_subject.txt",
            success_url=reverse_lazy("accounts:password_reset_done"),
        ),
        name="password_reset",
    ),
    path(
        "mot-de-passe/oublie/envoye/",
        auth_views.PasswordResetDoneView.as_view(template_name="accounts/password_reset_done.html"),
        name="password_reset_done",
    ),
    path(
        "mot-de-passe/reinitialiser/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="accounts/password_reset_confirm.html",
            success_url=reverse_lazy("accounts:password_reset_complete"),
        ),
        name="password_reset_confirm",
    ),
    path(
        "mot-de-passe/reinitialise/",
        auth_views.PasswordResetCompleteView.as_view(template_name="accounts/password_reset_complete.html"),
        name="password_reset_complete",
    ),
    path(
        "mot-de-passe/modifier/",
        auth_views.PasswordChangeView.as_view(
            template_name="accounts/password_change_form.html",
            success_url=reverse_lazy("accounts:password_change_done"),
        ),
        name="password_change",
    ),
    path(
        "mot-de-passe/modifie/",
        auth_views.PasswordChangeDoneView.as_view(template_name="accounts/password_change_done.html"),
        name="password_change_done",
    ),
    # Candidate
    path(
        "profil/candidat/",
        views.CandidateProfileUpdateView.as_view(),
        name="candidate_profile_update",
    ),
    path(
        "profil/candidat/competences-cv/",
        views.AddSuggestedSkillsView.as_view(),
        name="add_suggested_skills",
    ),
    path(
        "profil/candidat/parcours/",
        views.CandidateBackgroundView.as_view(),
        name="candidate_background",
    ),
    path(
        "candidats/<int:pk>/",
        views.CandidatePublicProfileView.as_view(),
        name="candidate_public_profile",
    ),
    # Recruiter & company
    path("profil/recruteur/", views.RecruiterAccountView.as_view(), name="recruiter_account"),
    path("entreprise/", views.CompanyUpdateView.as_view(), name="company_update"),
    path("entreprise/equipe/", views.CompanyTeamView.as_view(), name="company_team"),
    path(
        "entreprise/equipe/invitations/<int:pk>/annuler/",
        views.CancelInvitationView.as_view(),
        name="cancel_invitation",
    ),
    path(
        "entreprise/equipe/<int:pk>/retirer/",
        views.RemoveMemberView.as_view(),
        name="remove_member",
    ),
    path(
        "invitation/<uuid:token>/",
        views.AcceptInvitationView.as_view(),
        name="accept_invitation",
    ),
    path("entreprises/", views.CompanyListView.as_view(), name="company_list"),
    path("entreprises/<slug:slug>/", views.CompanyDetailView.as_view(), name="company_detail"),
]
