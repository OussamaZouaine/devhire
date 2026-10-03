from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from . import views

app_name = "api"

router = DefaultRouter()
router.register("offres", views.JobOfferViewSet, basename="joboffer")
router.register("candidatures", views.ApplicationViewSet, basename="application")
router.register("notifications", views.NotificationViewSet, basename="notification")
router.register("competences", views.SkillViewSet, basename="skill")
router.register("entreprises", views.CompanyViewSet, basename="company")

urlpatterns = [
    path("auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("moi/", views.MeView.as_view(), name="me"),
    path("moi/profil-candidat/", views.CandidateProfileView.as_view(), name="candidate_profile"),
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="api:schema"), name="swagger"),
    path("redoc/", SpectacularRedocView.as_view(url_name="api:schema"), name="redoc"),
    path("", include(router.urls)),
]
