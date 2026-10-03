import json
import os

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import CreateView, DetailView, FormView, TemplateView

from accounts.mixins import CandidateRequiredMixin, RecruiterRequiredMixin
from accounts.models import User
from jobs.models import JobOffer
from matching.services import match, rank_applications, top_candidates

from . import services
from .forms import ApplicationForm, InterviewForm, RecruiterNoteForm, StatusChangeForm
from .models import Application, Interview


def company_applications(user):
    """Applications the recruiter's company may manage."""
    return Application.objects.filter(job_offer__company=user.get_recruiter_profile().company)


class ApplyToJobView(CandidateRequiredMixin, CreateView):
    model = Application
    form_class = ApplicationForm
    template_name = "applications/apply_to_job.html"

    def dispatch(self, request, *args, **kwargs):
        self.job_offer = get_object_or_404(
            JobOffer.objects.open().select_related("company"),
            pk=kwargs["job_offer_id"],
        )
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["job_offer"] = self.job_offer
        context["has_quiz"] = hasattr(self.job_offer, "quiz") and self.job_offer.quiz.is_ready
        context["match"] = match(self.request.user.get_candidate_profile(), self.job_offer)
        return context

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
        application = services.submit_application(
            self.request.user.get_candidate_profile(),
            self.job_offer,
            form.cleaned_data["cover_letter"],
        )
        self.object = application
        messages.success(
            self.request,
            f"Votre candidature pour « {self.job_offer.title} » a été envoyée.",
        )
        quiz = getattr(self.job_offer, "quiz", None)
        if quiz is not None and quiz.is_ready:
            messages.info(self.request, "Cette offre comporte un test technique : vous pouvez le passer maintenant.")
            return redirect("assessments:quiz_start", application_id=application.pk)
        return redirect("applications:candidate_application_detail", pk=application.pk)


class CandidateApplicationDetailView(CandidateRequiredMixin, DetailView):
    template_name = "applications/candidate_application_detail.html"
    context_object_name = "application"

    def get_queryset(self):
        return (
            Application.objects.filter(candidate=self.request.user.get_candidate_profile())
            .select_related("job_offer__company")
            .prefetch_related("history", "interviews")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        application = self.object
        quiz = getattr(application.job_offer, "quiz", None)
        context["quiz"] = quiz if quiz is not None and quiz.is_ready else None
        context["quiz_attempt"] = getattr(application, "quiz_attempt", None)
        context["pipeline"] = [
            (status, status.label, Application.PIPELINE.index(status))
            for status in Application.PIPELINE
            if status != Application.Status.REJECTED
        ]
        if application.status in Application.PIPELINE:
            context["current_step"] = Application.PIPELINE.index(application.status)
        else:
            context["current_step"] = -1
        return context


class WithdrawApplicationView(CandidateRequiredMixin, View):
    def post(self, request, pk):
        application = get_object_or_404(Application, pk=pk, candidate=request.user.get_candidate_profile())
        if not application.can_be_withdrawn:
            messages.error(request, "Cette candidature ne peut plus être retirée.")
        else:
            services.withdraw(application)
            messages.info(request, "Votre candidature a été retirée.")
        return redirect("core:candidate_dashboard")


# ---------------------------------------------------------------- recruiter


class ApplicationPipelineView(RecruiterRequiredMixin, TemplateView):
    """Kanban board of the applications of one offer."""

    template_name = "applications/pipeline.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.role == User.Role.RECRUITER:
            self.job_offer = get_object_or_404(
                JobOffer, pk=kwargs["job_offer_id"], company=request.user.get_recruiter_profile().company
            )
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        applications = rank_applications(
            self.job_offer,
            Application.objects.filter(job_offer=self.job_offer)
            .exclude(status=Application.Status.WITHDRAWN)
            .select_related("quiz_attempt"),
        )
        columns = {status: [] for status in Application.PIPELINE}
        for application in applications:
            columns[application.status].append(application)
        context["job_offer"] = self.job_offer
        context["columns"] = [
            (status, status.label, Application.STATUS_COLORS[status], columns[status])
            for status in Application.PIPELINE
        ]
        context["application_count"] = len(applications)
        context["withdrawn_count"] = Application.objects.filter(
            job_offer=self.job_offer, status=Application.Status.WITHDRAWN
        ).count()
        context["top_candidates"] = top_candidates(self.job_offer)
        return context


class MoveApplicationView(RecruiterRequiredMixin, View):
    """Change the status of an application (Kanban drag & drop or form)."""

    def post(self, request, pk):
        application = get_object_or_404(
            company_applications(request.user).select_related("job_offer", "candidate__user"),
            pk=pk,
        )
        is_json = request.content_type == "application/json"
        data = json.loads(request.body or "{}") if is_json else request.POST
        form = StatusChangeForm(data)

        if application.status == Application.Status.WITHDRAWN:
            error = "Le candidat a retiré sa candidature."
        elif not form.is_valid():
            error = "Statut invalide."
        else:
            error = None

        if error:
            if is_json:
                return JsonResponse({"ok": False, "error": error}, status=400)
            messages.error(request, error)
            return redirect("applications:application_detail", pk=application.pk)

        changed = services.change_status(
            application, form.cleaned_data["status"], request.user, form.cleaned_data["note"]
        )
        if is_json:
            return JsonResponse(
                {
                    "ok": True,
                    "changed": changed,
                    "status": application.status,
                    "label": application.get_status_display(),
                }
            )
        if changed:
            messages.success(
                request,
                f"{application.candidate.user.display_name} → {application.get_status_display()}.",
            )
        next_url = request.POST.get("next")
        if next_url == "pipeline":
            return redirect("applications:pipeline", job_offer_id=application.job_offer_id)
        return redirect("applications:application_detail", pk=application.pk)


class ApplicationDetailView(RecruiterRequiredMixin, DetailView):
    template_name = "applications/application_detail.html"
    context_object_name = "application"

    def get_queryset(self):
        return (
            company_applications(self.request.user)
            .select_related("job_offer__company", "candidate__user")
            .prefetch_related(
                "candidate__skills",
                "candidate__experiences",
                "candidate__educations",
                "candidate__languages",
                "history__changed_by",
                "notes__author",
                "interviews",
            )
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        application = self.object
        context["match"] = match(application.candidate, application.job_offer)
        context["status_form"] = StatusChangeForm(initial={"status": application.status})
        context["note_form"] = RecruiterNoteForm()
        context["quiz_attempt"] = getattr(application, "quiz_attempt", None)
        return context


class AddRecruiterNoteView(RecruiterRequiredMixin, View):
    def post(self, request, pk):
        application = get_object_or_404(company_applications(request.user), pk=pk)
        form = RecruiterNoteForm(request.POST)
        if form.is_valid():
            note = form.save(commit=False)
            note.application = application
            note.author = request.user
            note.save()
            messages.success(request, "Note ajoutée.")
        else:
            messages.error(request, "La note ne peut pas être vide.")
        return redirect(reverse("applications:application_detail", kwargs={"pk": pk}) + "#notes")


class ScheduleInterviewView(RecruiterRequiredMixin, FormView):
    form_class = InterviewForm
    template_name = "applications/interview_form.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.role == User.Role.RECRUITER:
            self.application = get_object_or_404(
                company_applications(request.user).select_related("job_offer", "candidate__user"),
                pk=kwargs["pk"],
            )
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["application"] = self.application
        return context

    def form_valid(self, form):
        if self.application.is_closed:
            messages.error(self.request, "Cette candidature est clôturée.")
            return redirect("applications:application_detail", pk=self.application.pk)
        interview = form.save(commit=False)
        interview.application = self.application
        services.schedule_interview(interview, self.request.user)
        messages.success(self.request, "Entretien planifié, le candidat a été notifié.")
        return redirect("applications:application_detail", pk=self.application.pk)


class InterviewIcsView(View):
    """Download the interview as an .ics calendar file (candidate or company recruiters)."""

    def get(self, request, pk):
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        interview = get_object_or_404(
            Interview.objects.select_related("application__candidate", "application__job_offer__company"),
            pk=pk,
        )
        application = interview.application
        allowed = application.candidate.user_id == request.user.pk or application.job_offer.can_be_managed_by(
            request.user
        )
        if not allowed:
            raise PermissionDenied
        response = HttpResponse(services.interview_to_ics(interview), content_type="text/calendar; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="entretien-{interview.pk}.ics"'
        return response


class DownloadCvView(View):
    """Serve a candidate CV only to the company recruiters or the candidate."""

    def get(self, request, application_id):
        if not request.user.is_authenticated:
            return redirect("accounts:login")

        application = get_object_or_404(
            Application.objects.select_related(
                "candidate",
                "candidate__user",
                "job_offer",
                "job_offer__company",
            ),
            pk=application_id,
        )

        is_candidate = request.user.role == User.Role.CANDIDATE and application.candidate.user_id == request.user.id
        is_recruiter = application.job_offer.can_be_managed_by(request.user)

        if not (is_candidate or is_recruiter):
            raise PermissionDenied

        cv_file = application.candidate.cv
        if not cv_file:
            raise Http404("Aucun CV disponible pour cette candidature.")

        filename = os.path.basename(cv_file.name)
        return FileResponse(cv_file.open("rb"), as_attachment=True, filename=filename)
