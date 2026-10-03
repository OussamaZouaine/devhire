from django.conf import settings


def site_features(request):
    return {
        "google_login_enabled": bool(settings.GOOGLE_CLIENT_ID),
    }
