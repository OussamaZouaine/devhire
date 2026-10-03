"""
URL configuration for DevHire project.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("i18n/", include("django.conf.urls.i18n")),
    path("", include("core.urls")),
    path("compte/", include("accounts.urls")),
    path("auth/", include("allauth.urls")),
    path("offres/", include("jobs.urls")),
    path("candidatures/", include("applications.urls")),
    path("tests/", include("assessments.urls")),
    path("messagerie/", include("messaging.urls")),
    path("statistiques/", include("analytics.urls")),
    path("api/", include("api.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler404 = "core.views.page_not_found"
handler403 = "core.views.permission_denied"
