from django.urls import path

from . import views

app_name = "jobs"

urlpatterns = [
    path(
        "<int:pk>/",
        views.JobOfferDetailView.as_view(),
        name="job_offer_detail",
    ),
    path(
        "mes-offres/",
        views.RecruiterDashboardView.as_view(),
        name="recruiter_dashboard",
    ),
    path(
        "mes-offres/nouvelle/",
        views.JobOfferCreateView.as_view(),
        name="job_offer_create",
    ),
    path(
        "mes-offres/<int:pk>/modifier/",
        views.JobOfferUpdateView.as_view(),
        name="job_offer_update",
    ),
    path(
        "mes-offres/<int:pk>/basculer-statut/",
        views.JobOfferToggleActiveView.as_view(),
        name="job_offer_toggle_active",
    ),
]
