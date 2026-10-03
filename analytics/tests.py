from django.test import TestCase
from django.urls import reverse

from applications.models import Application
from assessments.models import Quiz, QuizAttempt
from core.factories import PASSWORD, make_application, make_candidate, make_offer, make_recruiter
from jobs.models import JobOfferView

from .services import company_dashboard, market_trends, percent


class AnalyticsTests(TestCase):
    def setUp(self):
        self.recruiter = make_recruiter("rec")
        self.company = self.recruiter.get_recruiter_profile().company
        self.offer = make_offer(self.recruiter, skills=["Python"], salary_min=40000, experience_level="mid")
        for index in range(4):
            JobOfferView.objects.create(job_offer=self.offer, session_key=f"s{index}")
        self.hired = make_application(make_candidate(skills=["Python"]), self.offer, match_score=80)
        self.hired.change_status(Application.Status.SHORTLISTED, changed_by=self.recruiter)
        self.hired.change_status(Application.Status.HIRED, changed_by=self.recruiter)
        self.rejected = make_application(make_candidate(), self.offer, match_score=20)
        self.rejected.change_status(Application.Status.REJECTED, changed_by=self.recruiter)
        quiz = Quiz.objects.create(job_offer=self.offer)
        QuizAttempt.objects.create(application=self.hired, quiz=quiz, score=90, submitted_at=self.hired.applied_at)

    def test_percent(self):
        self.assertEqual(percent(1, 3), 33.3)
        self.assertEqual(percent(1, 0), 0.0)

    def test_company_dashboard(self):
        data = company_dashboard(self.company, days=7)
        kpis = data["kpis"]
        self.assertEqual(kpis["views"], 4)
        self.assertEqual(kpis["applications"], 2)
        self.assertEqual(kpis["hired"], 1)
        self.assertEqual(kpis["view_to_application"], 50.0)
        self.assertEqual(kpis["application_to_hire"], 50.0)
        self.assertEqual(kpis["avg_match"], 50)
        self.assertEqual(kpis["quiz_avg"], 90)
        self.assertEqual(kpis["avg_response_days"], 0.0)
        funnel = {stage["status"]: stage["count"] for stage in data["funnel"]}
        self.assertEqual(funnel["received"], 2)
        self.assertEqual(funnel["shortlisted"], 1)
        self.assertEqual(funnel["hired"], 1)
        self.assertEqual(len(data["timeline"]["labels"]), 7)
        self.assertEqual(data["timeline"]["views"][-1], 4)
        self.assertEqual(data["timeline"]["applications"][-1], 2)
        self.assertEqual(data["per_offer"][0].conversion, 50.0)

    def test_market_trends(self):
        data = market_trends()
        self.assertEqual(data["totals"]["open_offers"], 1)
        self.assertEqual(data["by_city"], [{"label": "Paris", "count": 1}])
        skill = data["top_skills"][0]
        self.assertEqual((skill.name, skill.demand, skill.supply), ("Python", 1, 1))
        self.assertIn({"label": "Confirmé (2-5 ans)", "avg": 40000}, data["salary_by_level"])

    def test_pages(self):
        self.assertEqual(self.client.get(reverse("analytics:market_trends")).status_code, 200)
        self.client.login(username="rec", password=PASSWORD)
        response = self.client.get(reverse("analytics:recruiter_dashboard"), {"jours": "abc"})
        self.assertEqual(response.context["days"], 30)
        response = self.client.get(reverse("analytics:recruiter_dashboard"), {"jours": "7"})
        self.assertEqual(response.context["days"], 7)
