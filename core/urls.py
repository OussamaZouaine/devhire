from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.JobSearchListView.as_view(), name="home"),
    path(
        "mes-candidatures/",
        views.CandidateDashboardView.as_view(),
        name="candidate_dashboard",
    ),
]
