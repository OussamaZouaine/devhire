from django.urls import path

from . import views

app_name = "analytics"

urlpatterns = [
    path("recruteur/", views.RecruiterAnalyticsView.as_view(), name="recruiter_dashboard"),
    path("tendances/", views.MarketTrendsView.as_view(), name="market_trends"),
]
