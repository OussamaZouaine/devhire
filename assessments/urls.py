from django.urls import path

from . import views

app_name = "assessments"

urlpatterns = [
    path("offre/<int:job_offer_id>/", views.QuizManageView.as_view(), name="quiz_manage"),
    path("questions/<int:pk>/supprimer/", views.DeleteQuestionView.as_view(), name="delete_question"),
    path("candidature/<int:application_id>/", views.QuizStartView.as_view(), name="quiz_start"),
    path("candidature/<int:application_id>/passer/", views.QuizTakeView.as_view(), name="quiz_take"),
]
