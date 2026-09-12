from django.conf import settings
from django.http import HttpResponseForbidden


class ProtectCvMediaMiddleware:
    """
    Block direct access to uploaded CVs under /media/cvs/.
    CVs must be downloaded via the secured application view.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.cv_media_prefix = f"{settings.MEDIA_URL}cvs/"

    def __call__(self, request):
        if request.path.startswith(self.cv_media_prefix):
            return HttpResponseForbidden(
                "Accès direct aux CV interdit. Utilisez le lien de téléchargement "
                "depuis votre espace candidat ou recruteur."
            )
        return self.get_response(request)
