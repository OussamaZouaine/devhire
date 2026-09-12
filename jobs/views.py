from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from accounts.mixins import RecruiterRequiredMixin
from accounts.models import User
from applications.models import Application

from .forms import JobOfferForm
from .models import JobOffer


class RecruiterJobOfferMixin(RecruiterRequiredMixin):
    """Limit job offer access to the logged-in recruiter."""

    def get_recruiter(self):
        return self.request.user.get_recruiter_profile()

    def get_queryset(self):
        return JobOffer.objects.filter(recruiter=self.get_recruiter())


class RecruiterDashboardView(RecruiterJobOfferMixin, ListView):
    template_name = "jobs/recruiter_dashboard.html"
    context_object_name = "job_offers"

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .annotate(application_count=Count("applications"))
            .order_by("-created_at")
        )


class JobOfferCreateView(RecruiterRequiredMixin, CreateView):
    model = JobOffer
    form_class = JobOfferForm
    template_name = "jobs/job_offer_form.html"
    success_url = reverse_lazy("jobs:recruiter_dashboard")

    def form_valid(self, form):
        form.instance.recruiter = self.request.user.get_recruiter_profile()
        messages.success(self.request, "L'offre d'emploi a été créée avec succès.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form_title"] = "Publier une offre"
        return context


class JobOfferUpdateView(RecruiterJobOfferMixin, UpdateView):
    model = JobOffer
    form_class = JobOfferForm
    template_name = "jobs/job_offer_form.html"
    success_url = reverse_lazy("jobs:recruiter_dashboard")

    def form_valid(self, form):
        messages.success(self.request, "L'offre d'emploi a été mise à jour.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form_title"] = "Modifier l'offre"
        return context


class JobOfferToggleActiveView(RecruiterJobOfferMixin, View):
    """Activate or deactivate a job offer instead of deleting it."""

    def post(self, request, pk):
        offer = get_object_or_404(self.get_queryset(), pk=pk)
        offer.is_active = not offer.is_active
        offer.save(update_fields=["is_active", "updated_at"])

        if offer.is_active:
            messages.success(request, f"L'offre « {offer.title} » est maintenant active.")
        else:
            messages.info(request, f"L'offre « {offer.title} » a été désactivée.")

        return redirect("jobs:recruiter_dashboard")


class JobOfferDetailView(DetailView):
    model = JobOffer
    template_name = "jobs/job_offer_detail.html"
    context_object_name = "job_offer"

    def get_queryset(self):
        queryset = JobOffer.objects.select_related("recruiter")
        user = self.request.user

        if user.is_authenticated and user.role == User.Role.CANDIDATE:
            profile = user.get_candidate_profile()
            applied_offer_ids = Application.objects.filter(
                candidate=profile
            ).values_list("job_offer_id", flat=True)
            return queryset.filter(Q(is_active=True) | Q(pk__in=applied_offer_ids))

        return queryset.filter(is_active=True)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context["can_apply"] = False
        context["has_applied"] = False
        context["missing_cv"] = False

        if user.is_authenticated and user.role == User.Role.CANDIDATE:
            profile = user.get_candidate_profile()
            context["has_applied"] = Application.objects.filter(
                candidate=profile,
                job_offer=self.object,
            ).exists()
            context["missing_cv"] = not bool(profile.cv)
            context["can_apply"] = (
                self.object.is_active
                and not context["has_applied"]
                and not context["missing_cv"]
            )

        return context
