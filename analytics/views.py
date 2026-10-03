from django.views.generic import TemplateView

from accounts.mixins import RecruiterRequiredMixin

from .services import company_dashboard, market_trends

PERIODS = (7, 30, 90)


class RecruiterAnalyticsView(RecruiterRequiredMixin, TemplateView):
    template_name = "analytics/recruiter_dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            days = int(self.request.GET.get("jours", 30))
        except ValueError:
            days = 30
        days = days if days in PERIODS else 30
        context.update(company_dashboard(self.get_company(), days=days))
        context["company"] = self.get_company()
        context["days"] = days
        context["periods"] = PERIODS
        return context


class MarketTrendsView(TemplateView):
    template_name = "analytics/market_trends.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(market_trends())
        return context
