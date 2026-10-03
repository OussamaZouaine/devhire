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
        "<int:pk>/favori/",
        views.ToggleSavedJobView.as_view(),
        name="toggle_saved_job",
    ),
    path("favoris/", views.SavedJobListView.as_view(), name="saved_jobs"),
    path("alertes/", views.JobAlertListView.as_view(), name="job_alert_list"),
    path("alertes/nouvelle/", views.JobAlertCreateView.as_view(), name="job_alert_create"),
    path("alertes/<int:pk>/modifier/", views.JobAlertUpdateView.as_view(), name="job_alert_update"),
    path("alertes/<int:pk>/supprimer/", views.JobAlertDeleteView.as_view(), name="job_alert_delete"),
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
