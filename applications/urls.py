from django.urls import path

from . import views

app_name = "applications"

urlpatterns = [
    path(
        "postuler/<int:job_offer_id>/",
        views.ApplyToJobView.as_view(),
        name="apply_to_job",
    ),
    path(
        "offre/<int:job_offer_id>/",
        views.JobApplicationsListView.as_view(),
        name="job_applications_list",
    ),
    path(
        "<int:pk>/statut/",
        views.UpdateApplicationStatusView.as_view(),
        name="update_application_status",
    ),
    path(
        "<int:application_id>/cv/",
        views.DownloadCvView.as_view(),
        name="download_cv",
    ),
]
