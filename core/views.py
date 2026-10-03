from django.core.paginator import Paginator
from django.shortcuts import render
from django.utils import timezone
from django.views.generic import ListView, TemplateView

from accounts.mixins import CandidateRequiredMixin
from applications.models import Application, Interview
from jobs.forms import JobSearchForm
from jobs.models import JobOffer, SavedJob
from jobs.search import search_offers, uses_full_text_search
from matching.services import recommend_offers, score_offers_for_candidate

MAX_MATCH_SORTED_RESULTS = 300


class JobSearchListView(ListView):
    """Home page — search and browse open job offers."""

    model = JobOffer
    template_name = "core/job_search.html"
    context_object_name = "job_offers"
    paginate_by = 10

    def get_form(self) -> JobSearchForm:
        if not hasattr(self, "_form"):
            self._form = JobSearchForm(self.request.GET or None)
        return self._form

    def is_candidate(self) -> bool:
        user = self.request.user
        return user.is_authenticated and user.is_candidate

    def get_queryset(self):
        return search_offers(self.get_form().filters())

    def paginate_queryset(self, queryset, page_size):
        """Sorting by compatibility needs every result scored first."""
        if self.get_form().filters().get("sort") == "match" and self.is_candidate():
            offers = list(queryset[:MAX_MATCH_SORTED_RESULTS])
            self.scores = score_offers_for_candidate(self.request.user.get_candidate_profile(), offers)
            offers.sort(key=lambda offer: self.scores[offer.pk].score, reverse=True)
            queryset = offers
        return super().paginate_queryset(queryset, page_size)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = self.get_form()
        filters = form.filters()
        context["form"] = form
        context["filters"] = filters
        context["has_filters"] = any(key != "sort" for key in filters)
        context["contract_types"] = JobOffer.ContractType.choices
        context["remote_policies"] = JobOffer.RemotePolicy.choices
        context["experience_levels"] = JobOffer.ExperienceLevel.choices
        context["full_text_search"] = uses_full_text_search()
        paginator = context.get("paginator")
        context["total_results"] = paginator.count if paginator else len(context["job_offers"])

        page_offers = list(context["job_offers"])
        if self.is_candidate():
            profile = self.request.user.get_candidate_profile()
            scores = getattr(self, "scores", None) or score_offers_for_candidate(profile, page_offers)
            context["scores"] = scores
            context["saved_ids"] = set(
                SavedJob.objects.filter(candidate=profile).values_list("job_offer_id", flat=True)
            )
            for offer in page_offers:
                offer.match = scores.get(offer.pk)
        return context


class CandidateDashboardView(CandidateRequiredMixin, TemplateView):
    template_name = "core/candidate_dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile = self.request.user.get_candidate_profile()
        applications = Application.objects.filter(candidate=profile).select_related(
            "job_offer__company", "job_offer__quiz", "quiz_attempt"
        )
        paginator = Paginator(applications, 10)
        context["page_obj"] = paginator.get_page(self.request.GET.get("page"))
        context["applications"] = context["page_obj"].object_list
        context["profile"] = profile
        context["recommendations"] = recommend_offers(profile, limit=4)
        context["upcoming_interviews"] = Interview.objects.filter(
            application__candidate=profile, scheduled_at__gte=timezone.now()
        ).select_related("application__job_offer__company")[:5]
        context["saved_count"] = SavedJob.objects.filter(candidate=profile).count()
        context["alert_count"] = profile.job_alerts.filter(is_active=True).count()
        context["stats"] = {
            "total": applications.count(),
            "in_progress": applications.exclude(status__in=Application.CLOSED_STATUSES).count(),
            "interviews": applications.filter(status=Application.Status.INTERVIEW).count(),
        }
        return context


def page_not_found(request, exception):
    return render(request, "404.html", status=404)


def permission_denied(request, exception):
    return render(request, "403.html", status=403)
