import os

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, ListView

from accounts.mixins import CandidateRequiredMixin, RecruiterRequiredMixin
from accounts.models import User
from jobs.models import JobOffer

from .forms import ApplicationForm
from .models import Application


class ApplyToJobView(CandidateRequiredMixin, CreateView):
    model = Application
    form_class = ApplicationForm
    template_name = "applications/apply_to_job.html"

    def dispatch(self, request, *args, **kwargs):
        self.job_offer = get_object_or_404(
            JobOffer,
            pk=kwargs["job_offer_id"],
            is_active=True,
        )
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["job_offer"] = self.job_offer
        return context

    def get_success_url(self):
        return reverse_lazy("core:candidate_dashboard")

    def _check_apply_eligibility(self, request):
        profile = request.user.get_candidate_profile()

        if not profile.cv:
            messages.warning(
                request,
                "Vous devez téléverser votre CV avant de postuler à une offre.",
            )
            return redirect("accounts:candidate_profile_update")

        if Application.objects.filter(
            candidate=profile,
            job_offer=self.job_offer,
        ).exists():
            messages.error(request, "Vous avez déjà postulé à cette offre.")
            return redirect("jobs:job_offer_detail", pk=self.job_offer.pk)

        return None

    def get(self, request, *args, **kwargs):
        redirect_response = self._check_apply_eligibility(request)
        if redirect_response:
            return redirect_response
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        redirect_response = self._check_apply_eligibility(request)
        if redirect_response:
            return redirect_response
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.candidate = self.request.user.get_candidate_profile()
        form.instance.job_offer = self.job_offer
        form.instance.status = Application.Status.PENDING
        messages.success(
            self.request,
            f"Votre candidature pour « {self.job_offer.title} » a été envoyée.",
        )
        return super().form_valid(form)


class JobApplicationsListView(RecruiterRequiredMixin, ListView):
    model = Application
    template_name = "applications/job_applications_list.html"
    context_object_name = "applications"

    def dispatch(self, request, *args, **kwargs):
        self.job_offer = get_object_or_404(
            JobOffer,
            pk=kwargs["job_offer_id"],
            recruiter=request.user.get_recruiter_profile(),
        )
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return (
            Application.objects.filter(job_offer=self.job_offer)
            .select_related("candidate", "candidate__user")
            .order_by("-applied_at")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["job_offer"] = self.job_offer
        return context


class UpdateApplicationStatusView(RecruiterRequiredMixin, View):
    """Accept or reject an application (POST only)."""

    def post(self, request, pk):
        application = get_object_or_404(
            Application.objects.select_related("job_offer"),
            pk=pk,
            job_offer__recruiter=request.user.get_recruiter_profile(),
        )

        action = request.POST.get("action")
        if action == "accept":
            application.status = Application.Status.ACCEPTED
            application.save(update_fields=["status"])
            messages.success(
                request,
                f"Candidature de {application.candidate.user.username} acceptée.",
            )
        elif action == "reject":
            application.status = Application.Status.REJECTED
            application.save(update_fields=["status"])
            messages.warning(
                request,
                f"Candidature de {application.candidate.user.username} refusée.",
            )
        else:
            messages.error(request, "Action invalide.")
            return redirect(
                "applications:job_applications_list",
                job_offer_id=application.job_offer_id,
            )

        return redirect(
            "applications:job_applications_list",
            job_offer_id=application.job_offer_id,
        )


class DownloadCvView(View):
    """Serve a candidate CV only to the owner recruiter or the candidate."""

    def get(self, request, application_id):
        if not request.user.is_authenticated:
            return redirect("accounts:login")

        application = get_object_or_404(
            Application.objects.select_related(
                "candidate",
                "candidate__user",
                "job_offer",
                "job_offer__recruiter",
                "job_offer__recruiter__user",
            ),
            pk=application_id,
        )

        is_candidate = (
            request.user.role == User.Role.CANDIDATE
            and application.candidate.user_id == request.user.id
        )
        is_recruiter = (
            request.user.role == User.Role.RECRUITER
            and application.job_offer.recruiter.user_id == request.user.id
        )

        if not (is_candidate or is_recruiter):
            raise PermissionDenied

        cv_file = application.candidate.cv
        if not cv_file:
            raise Http404("Aucun CV disponible pour cette candidature.")

        filename = os.path.basename(cv_file.name)
        return FileResponse(cv_file.open("rb"), as_attachment=True, filename=filename)
