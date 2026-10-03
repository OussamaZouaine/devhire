from contextlib import suppress

from django.contrib import messages
from django.db import IntegrityError
from django.db.models import Count, Q
from django.forms import Form
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from accounts.mixins import CandidateRequiredMixin, RecruiterRequiredMixin
from accounts.models import User
from applications.models import Application
from matching.services import match

from .forms import JobAlertForm, JobOfferForm
from .models import JobAlert, JobOffer, JobOfferView, SavedJob


class RecruiterJobOfferMixin(RecruiterRequiredMixin):
    """Limit job offer access to the offers of the recruiter's company."""

    def get_queryset(self):
        return JobOffer.objects.filter(company=self.get_company())


class RecruiterDashboardView(RecruiterJobOfferMixin, ListView):
    template_name = "jobs/recruiter_dashboard.html"
    context_object_name = "job_offers"

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related("recruiter__user")
            .annotate(
                application_count=Count("applications", distinct=True),
                new_application_count=Count(
                    "applications",
                    filter=Q(applications__status=Application.Status.RECEIVED),
                    distinct=True,
                ),
                view_count=Count("views", distinct=True),
            )
            .order_by("-created_at")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["company"] = self.get_company()
        return context


class JobOfferCreateView(RecruiterRequiredMixin, CreateView):
    model = JobOffer
    form_class = JobOfferForm
    template_name = "jobs/job_offer_form.html"
    success_url = reverse_lazy("jobs:recruiter_dashboard")

    def form_valid(self, form):
        recruiter = self.get_recruiter()
        form.instance.recruiter = recruiter
        form.instance.company = recruiter.company
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


def record_offer_view(request, offer: JobOffer) -> None:
    """Count one view per session and per day; recruiters of the company are ignored."""
    user = request.user
    if offer.can_be_managed_by(user):
        return
    if not request.session.session_key:
        request.session.save()
    with suppress(IntegrityError):
        JobOfferView.objects.get_or_create(
            job_offer=offer,
            session_key=request.session.session_key,
            defaults={"user": user if user.is_authenticated else None},
        )


class JobOfferDetailView(DetailView):
    model = JobOffer
    template_name = "jobs/job_offer_detail.html"
    context_object_name = "job_offer"

    def get_queryset(self):
        queryset = JobOffer.objects.select_related("company", "recruiter__user").prefetch_related("skills")
        user = self.request.user

        if user.is_authenticated and user.role == User.Role.RECRUITER:
            return queryset.filter(Q(is_active=True) | Q(company=user.get_recruiter_profile().company))

        if user.is_authenticated and user.role == User.Role.CANDIDATE:
            profile = user.get_candidate_profile()
            applied_offer_ids = Application.objects.filter(candidate=profile).values_list("job_offer_id", flat=True)
            return queryset.filter(Q(is_active=True) | Q(pk__in=applied_offer_ids))

        return queryset.filter(is_active=True)

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        record_offer_view(request, self.object)
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        offer = self.object
        user = self.request.user
        context["can_apply"] = False
        context["has_applied"] = False
        context["missing_cv"] = False
        context["is_saved"] = False
        context["can_manage"] = offer.can_be_managed_by(user)
        context["has_quiz"] = hasattr(offer, "quiz") and offer.quiz.is_ready

        if user.is_authenticated and user.role == User.Role.CANDIDATE:
            profile = user.get_candidate_profile()
            application = Application.objects.filter(candidate=profile, job_offer=offer).first()
            context["application"] = application
            context["has_applied"] = application is not None
            context["missing_cv"] = not bool(profile.cv)
            context["is_saved"] = SavedJob.objects.filter(candidate=profile, job_offer=offer).exists()
            context["can_apply"] = offer.is_open and not context["has_applied"] and not context["missing_cv"]
            context["match"] = match(profile, offer)

        context["similar_offers"] = (
            JobOffer.objects.open()
            .exclude(pk=offer.pk)
            .filter(skills__in=offer.skills.all())
            .annotate(common=Count("skills"))
            .select_related("company")
            .order_by("-common", "-created_at")[:4]
        )
        return context


class ToggleSavedJobView(CandidateRequiredMixin, View):
    def post(self, request, pk):
        offer = get_object_or_404(JobOffer, pk=pk)
        profile = request.user.get_candidate_profile()
        saved, created = SavedJob.objects.get_or_create(candidate=profile, job_offer=offer)
        if created:
            messages.success(request, f"« {offer.title} » ajoutée à vos favoris.")
        else:
            saved.delete()
            messages.info(request, f"« {offer.title} » retirée de vos favoris.")
        next_url = request.POST.get("next")
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
            return redirect(next_url)
        return redirect(offer.get_absolute_url())


class SavedJobListView(CandidateRequiredMixin, ListView):
    template_name = "jobs/saved_jobs.html"
    context_object_name = "saved_jobs"

    def get_queryset(self):
        return SavedJob.objects.filter(candidate=self.request.user.get_candidate_profile()).select_related(
            "job_offer__company"
        )


class JobAlertMixin(CandidateRequiredMixin):
    model = JobAlert
    form_class = JobAlertForm
    success_url = reverse_lazy("jobs:job_alert_list")

    def get_queryset(self):
        return JobAlert.objects.filter(candidate=self.request.user.get_candidate_profile())


class JobAlertListView(JobAlertMixin, ListView):
    template_name = "jobs/job_alert_list.html"
    context_object_name = "alerts"


class JobAlertCreateView(JobAlertMixin, CreateView):
    template_name = "jobs/job_alert_form.html"

    def get_initial(self):
        """Pre-fill the alert from the current search (link "Créer une alerte")."""
        initial = super().get_initial()
        for field in ("query", "location", "contract_type", "remote_policy", "salary_min"):
            source = "q" if field == "query" else field
            if value := self.request.GET.get(source):
                initial[field] = value
        if initial.get("query") or initial.get("location"):
            initial["name"] = " · ".join(filter(None, [initial.get("query"), initial.get("location")]))
        return initial

    def form_valid(self, form):
        form.instance.candidate = self.request.user.get_candidate_profile()
        messages.success(self.request, "Alerte créée : vous recevrez les nouvelles offres par email.")
        return super().form_valid(form)


class JobAlertUpdateView(JobAlertMixin, UpdateView):
    template_name = "jobs/job_alert_form.html"

    def form_valid(self, form):
        messages.success(self.request, "Alerte mise à jour.")
        return super().form_valid(form)


class JobAlertDeleteView(JobAlertMixin, DeleteView):
    template_name = "jobs/job_alert_confirm_delete.html"
    form_class = Form  # DeleteView only needs an empty confirmation form

    def form_valid(self, form):
        messages.info(self.request, "Alerte supprimée.")
        return super().form_valid(form)
