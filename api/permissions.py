from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsCandidate(BasePermission):
    message = "Réservé aux candidats."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_candidate)


class IsRecruiter(BasePermission):
    message = "Réservé aux recruteurs."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_recruiter)


class IsCompanyRecruiterOrReadOnly(BasePermission):
    """Anyone can read; only recruiters of the offer's company can write."""

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return IsRecruiter().has_permission(request, view)

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return obj.can_be_managed_by(request.user)
