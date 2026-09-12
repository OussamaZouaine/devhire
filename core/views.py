from django.db.models import Q
from django.shortcuts import render
from django.views.generic import ListView

from accounts.mixins import CandidateRequiredMixin
from applications.models import Application
from jobs.models import JobOffer


class JobSearchListView(ListView):
    """Home page — search and browse active job offers."""

    model = JobOffer
    template_name = "core/job_search.html"
    context_object_name = "job_offers"
    paginate_by = 10

    def get_queryset(self):
        queryset = (
            JobOffer.objects.filter(is_active=True)
            .select_related("recruiter")
            .order_by("-created_at")
        )

        query = self.request.GET.get("q", "").strip()
        location = self.request.GET.get("location", "").strip()
        contract_type = self.request.GET.get("contract_type", "").strip()

        if query:
            queryset = queryset.filter(
                Q(title__icontains=query)
                | Q(keywords__icontains=query)
                | Q(description__icontains=query)
            )

        if location:
            queryset = queryset.filter(location__icontains=location)

        if contract_type:
            queryset = queryset.filter(contract_type=contract_type)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["search_q"] = self.request.GET.get("q", "")
        context["search_location"] = self.request.GET.get("location", "")
        context["search_contract_type"] = self.request.GET.get("contract_type", "")
        context["contract_types"] = JobOffer.ContractType.choices
        paginator = context.get("paginator")
        if paginator:
            context["total_results"] = paginator.count
        else:
            job_offers = context["job_offers"]
            context["total_results"] = (
                job_offers.count() if hasattr(job_offers, "count") else len(job_offers)
            )
        return context


class CandidateDashboardView(CandidateRequiredMixin, ListView):
    template_name = "core/candidate_dashboard.html"
    context_object_name = "applications"

    def get_queryset(self):
        return Application.objects.filter(
            candidate=self.request.user.get_candidate_profile()
        ).select_related("job_offer", "job_offer__recruiter")


def page_not_found(request, exception):
    return render(request, "404.html", status=404)


def permission_denied(request, exception):
    return render(request, "403.html", status=403)
