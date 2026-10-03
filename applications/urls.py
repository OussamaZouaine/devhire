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
        "mes-candidatures/<int:pk>/",
        views.CandidateApplicationDetailView.as_view(),
        name="candidate_application_detail",
    ),
    path(
        "mes-candidatures/<int:pk>/retirer/",
        views.WithdrawApplicationView.as_view(),
        name="withdraw",
    ),
    path(
        "offre/<int:job_offer_id>/",
        views.ApplicationPipelineView.as_view(),
        name="pipeline",
    ),
    path(
        "<int:pk>/",
        views.ApplicationDetailView.as_view(),
        name="application_detail",
    ),
    path(
        "<int:pk>/statut/",
        views.MoveApplicationView.as_view(),
        name="update_application_status",
    ),
    path(
        "<int:pk>/notes/",
        views.AddRecruiterNoteView.as_view(),
        name="add_note",
    ),
    path(
        "<int:pk>/entretien/",
        views.ScheduleInterviewView.as_view(),
        name="schedule_interview",
    ),
    path(
        "entretiens/<int:pk>/calendrier.ics",
        views.InterviewIcsView.as_view(),
        name="interview_ics",
    ),
    path(
        "<int:application_id>/cv/",
        views.DownloadCvView.as_view(),
        name="download_cv",
    ),
]
