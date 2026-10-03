from django.db.models import Q
from django_filters import rest_framework as filters
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from accounts.models import Company
from applications import services as application_services
from applications.models import Application
from jobs.models import JobOffer
from jobs.search import search_offers
from matching.models import Skill
from matching.services import match, recommend_offers
from messaging.models import Notification

from .permissions import IsCandidate, IsCompanyRecruiterOrReadOnly, IsRecruiter
from .serializers import (
    ApplicationSerializer,
    CandidateProfileSerializer,
    CompanySerializer,
    JobOfferSerializer,
    MatchSerializer,
    NotificationSerializer,
    RecommendationSerializer,
    SkillSerializer,
    StatusUpdateSerializer,
    UserSerializer,
)

SEARCH_PARAMS = ("q", "location", "contract_type", "remote_policy", "experience_level", "salary_min", "skill", "sort")


class SkillViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Skill.objects.all()
    serializer_class = SkillSerializer
    pagination_class = None

    def get_queryset(self):
        queryset = super().get_queryset()
        if query := self.request.query_params.get("q"):
            queryset = queryset.filter(name__icontains=query)
        return queryset[:50]


class CompanyViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Company.objects.all()
    serializer_class = CompanySerializer
    lookup_field = "slug"


class JobOfferViewSet(viewsets.ModelViewSet):
    """
    Public listing of open offers (same filters as the website search).
    Recruiters can create offers and edit those of their company.
    """

    serializer_class = JobOfferSerializer
    permission_classes = [IsCompanyRecruiterOrReadOnly]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        user = self.request.user
        if self.action == "list":
            params = {key: self.request.query_params.get(key) for key in SEARCH_PARAMS}
            params = {key: value for key, value in params.items() if value}
            return search_offers(params)
        queryset = JobOffer.objects.select_related("company").prefetch_related("skills")
        if user.is_authenticated and user.is_recruiter:
            return queryset.filter(Q(is_active=True) | Q(company=user.get_recruiter_profile().company))
        return queryset.filter(is_active=True)

    @extend_schema(parameters=[OpenApiParameter(name, str, required=False) for name in SEARCH_PARAMS])
    def list(self, request, *args, **kwargs):
        if request.query_params.get("salary_min") and not request.query_params["salary_min"].isdigit():
            raise ValidationError({"salary_min": "Doit être un entier."})
        return super().list(request, *args, **kwargs)

    def perform_create(self, serializer):
        recruiter = self.request.user.get_recruiter_profile()
        serializer.save(company=recruiter.company, recruiter=recruiter)

    @extend_schema(responses=JobOfferSerializer(many=True))
    @action(detail=False, permission_classes=[IsRecruiter])
    def mine(self, request):
        """Offers of the recruiter's company (active or not)."""
        queryset = JobOffer.objects.filter(company=request.user.get_recruiter_profile().company).prefetch_related(
            "skills"
        )
        page = self.paginate_queryset(queryset)
        return self.get_paginated_response(self.get_serializer(page, many=True).data)

    @extend_schema(responses=RecommendationSerializer(many=True))
    @action(detail=False, permission_classes=[IsCandidate])
    def recommended(self, request):
        """Best matching open offers for the logged-in candidate."""
        results = recommend_offers(request.user.get_candidate_profile(), limit=10)
        data = [{"offer": offer, "match": result} for offer, result in results]
        return Response(RecommendationSerializer(data, many=True, context={"request": request}).data)

    @extend_schema(responses=MatchSerializer)
    @action(detail=True, permission_classes=[IsCandidate], url_path="match")
    def match_score(self, request, pk=None):
        """Compatibility between the logged-in candidate and this offer."""
        result = match(request.user.get_candidate_profile(), self.get_object())
        return Response(MatchSerializer(result).data)


class ApplicationFilter(filters.FilterSet):
    class Meta:
        model = Application
        fields = ("status", "job_offer")


class ApplicationViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    """
    Candidates: their own applications (create = apply).
    Recruiters: the applications received by their company.
    """

    serializer_class = ApplicationSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_class = ApplicationFilter
    ordering_fields = ("applied_at", "match_score")

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Application.objects.none()
        user = self.request.user
        queryset = Application.objects.select_related("job_offer__company", "candidate__user")
        if user.is_candidate:
            return queryset.filter(candidate__user=user)
        if user.is_recruiter:
            return queryset.filter(job_offer__company=user.get_recruiter_profile().company)
        return queryset.none()

    def create(self, request, *args, **kwargs):
        if not request.user.is_candidate:
            return Response({"detail": "Réservé aux candidats."}, status=status.HTTP_403_FORBIDDEN)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = request.user.get_candidate_profile()
        offer = serializer.validated_data["job_offer"]
        if not profile.cv:
            raise ValidationError({"detail": "Téléversez votre CV avant de postuler."})
        if Application.objects.filter(candidate=profile, job_offer=offer).exists():
            raise ValidationError({"detail": "Vous avez déjà postulé à cette offre."})
        application = application_services.submit_application(
            profile, offer, serializer.validated_data.get("cover_letter", "")
        )
        return Response(self.get_serializer(application).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=StatusUpdateSerializer, responses=ApplicationSerializer)
    @action(detail=True, methods=["post"], permission_classes=[IsRecruiter], url_path="status")
    def change_status(self, request, pk=None):
        application = self.get_object()
        if application.status == Application.Status.WITHDRAWN:
            raise ValidationError({"detail": "Le candidat a retiré sa candidature."})
        serializer = StatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        application_services.change_status(
            application,
            serializer.validated_data["status"],
            request.user,
            serializer.validated_data.get("note", ""),
        )
        return Response(self.get_serializer(application).data)

    @extend_schema(request=None, responses=ApplicationSerializer)
    @action(detail=True, methods=["post"], permission_classes=[IsCandidate])
    def withdraw(self, request, pk=None):
        application = self.get_object()
        if not application.can_be_withdrawn:
            raise ValidationError({"detail": "Cette candidature ne peut plus être retirée."})
        application_services.withdraw(application)
        return Response(self.get_serializer(application).data)


class NotificationViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Notification.objects.none()
        queryset = self.request.user.notifications.all()
        if self.request.query_params.get("unread") in ("1", "true"):
            queryset = queryset.filter(is_read=False)
        return queryset

    @extend_schema(request=None, responses=None)
    @action(detail=True, methods=["post"])
    def read(self, request, pk=None):
        self.get_queryset().filter(pk=pk).update(is_read=True)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(request=None, responses=None)
    @action(detail=False, methods=["post"], url_path="read-all")
    def read_all(self, request):
        self.get_queryset().update(is_read=True)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(generics.RetrieveUpdateAPIView):
    """Logged-in user. Candidates also get their profile."""

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self):
        return self.request.user

    def retrieve(self, request, *args, **kwargs):
        data = UserSerializer(request.user).data
        if request.user.is_candidate:
            data["candidate_profile"] = CandidateProfileSerializer(request.user.get_candidate_profile()).data
        elif request.user.is_recruiter:
            data["company"] = CompanySerializer(request.user.get_recruiter_profile().company).data
        return Response(data)


class CandidateProfileView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsCandidate]
    serializer_class = CandidateProfileSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self):
        return self.request.user.get_candidate_profile()
