from datetime import timedelta
from unittest import skipUnless

from django.core import mail
from django.db import connection
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.factories import PASSWORD, make_candidate, make_company, make_offer, make_recruiter
from messaging.models import Notification

from .models import JobAlert, JobOffer, JobOfferView, SavedJob
from .search import search_offers
from .tasks import send_job_alerts


class RecruiterOfferTests(TestCase):
    def setUp(self):
        self.company = make_company("Acme")
        self.recruiter = make_recruiter("rec_a", company=self.company)
        self.colleague = make_recruiter("rec_b", company=self.company, admin=False)
        self.outsider = make_recruiter("rec_c")
        self.offer = make_offer(self.recruiter, title="Dev Django")

    def test_create_offer_with_skills(self):
        self.client.login(username="rec_a", password=PASSWORD)
        response = self.client.post(
            reverse("jobs:job_offer_create"),
            {
                "title": "Dev React",
                "description": "Front",
                "location": "Lyon",
                "contract_type": "CDD",
                "remote_policy": "remote",
                "experience_level": "mid",
                "skills": "React, TypeScript",
                "is_active": True,
            },
        )
        self.assertRedirects(response, reverse("jobs:recruiter_dashboard"))
        offer = JobOffer.objects.get(title="Dev React")
        self.assertEqual(offer.company, self.company)
        self.assertEqual(sorted(offer.skill_names), ["React", "TypeScript"])

    def test_form_validation(self):
        self.client.login(username="rec_a", password=PASSWORD)
        response = self.client.post(
            reverse("jobs:job_offer_create"),
            {
                "title": "X",
                "description": "Y",
                "location": "Z",
                "contract_type": "CDI",
                "remote_policy": "onsite",
                "experience_level": "junior",
                "salary_min": 50000,
                "salary_max": 40000,
                "deadline": (timezone.localdate() - timedelta(days=1)).isoformat(),
            },
        )
        form = response.context["form"]
        self.assertIn("salary_max", form.errors)
        self.assertIn("deadline", form.errors)

    def test_colleague_can_edit_but_outsider_cannot(self):
        url = reverse("jobs:job_offer_update", args=[self.offer.pk])
        self.client.login(username="rec_b", password=PASSWORD)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.login(username="rec_c", password=PASSWORD)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_toggle_active(self):
        self.client.login(username="rec_a", password=PASSWORD)
        self.client.post(reverse("jobs:job_offer_toggle_active", args=[self.offer.pk]))
        self.offer.refresh_from_db()
        self.assertFalse(self.offer.is_active)
        self.client.post(reverse("jobs:job_offer_toggle_active", args=[self.offer.pk]))
        self.offer.refresh_from_db()
        self.assertTrue(self.offer.is_active)

    def test_dashboard_lists_company_offers(self):
        make_offer(self.outsider, title="Other company")
        self.client.login(username="rec_b", password=PASSWORD)
        response = self.client.get(reverse("jobs:recruiter_dashboard"))
        self.assertEqual(list(response.context["job_offers"]), [self.offer])

    def test_recruiter_sees_own_inactive_offer(self):
        self.offer.is_active = False
        self.offer.save()
        url = reverse("jobs:job_offer_detail", args=[self.offer.pk])
        self.client.login(username="rec_b", password=PASSWORD)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.login(username="rec_c", password=PASSWORD)
        self.assertEqual(self.client.get(url).status_code, 404)


class OfferViewTrackingTests(TestCase):
    def setUp(self):
        self.recruiter = make_recruiter("rec")
        self.offer = make_offer(self.recruiter)
        self.url = reverse("jobs:job_offer_detail", args=[self.offer.pk])

    def test_one_view_per_session_per_day(self):
        self.client.get(self.url)
        self.client.get(self.url)
        self.assertEqual(JobOfferView.objects.count(), 1)

    def test_company_recruiters_are_not_counted(self):
        self.client.login(username="rec", password=PASSWORD)
        self.client.get(self.url)
        self.assertEqual(JobOfferView.objects.count(), 0)

    def test_candidate_detail_has_match_and_similar_offers(self):
        similar = make_offer(self.recruiter, skills=["Python"])
        self.offer.skills.set(similar.skills.all())
        make_candidate("alice", skills=["Python"])
        self.client.login(username="alice", password=PASSWORD)
        response = self.client.get(self.url)
        self.assertEqual(response.context["match"].skill_score, 100)
        self.assertIn(similar, response.context["similar_offers"])
        self.assertTrue(response.context["can_apply"])


class SearchTests(TestCase):
    def setUp(self):
        recruiter = make_recruiter()
        self.django = make_offer(
            recruiter,
            title="Développeur Django",
            skills=["Python", "Django"],
            location="Paris",
            remote_policy="hybrid",
            salary_min=40000,
            salary_max=50000,
        )
        self.react = make_offer(
            recruiter,
            title="Développeur React",
            skills=["React"],
            location="Lyon",
            contract_type="CDD",
            salary_min=35000,
            salary_max=38000,
        )
        self.expired = make_offer(
            recruiter, title="Expired Django", skills=["Django"], deadline=timezone.localdate() - timedelta(days=1)
        )

    def search(self, **filters):
        return list(search_offers(filters))

    def test_filters(self):
        self.assertEqual(self.search(q="django"), [self.django])
        self.assertEqual(self.search(q="react"), [self.react])
        self.assertEqual(self.search(location="lyon"), [self.react])
        self.assertEqual(self.search(contract_type="CDD"), [self.react])
        self.assertEqual(self.search(remote_policy="hybrid"), [self.django])
        self.assertEqual(self.search(salary_min=45000), [self.django])
        self.assertEqual(self.search(skill="python"), [self.django])
        self.assertEqual(self.search(sort="salary")[0], self.django)

    @skipUnless(connection.vendor == "postgresql", "Recherche plein texte PostgreSQL uniquement")
    def test_full_text_search_uses_stemming_and_relevance(self):
        # "développeurs" (plural) matches "Développeur" thanks to the French stemmer.
        self.assertEqual(set(self.search(q="développeurs")), {self.django, self.react})
        self.assertEqual(self.search(q="django", sort="relevance")[0], self.django)

    def test_expired_offers_are_hidden(self):
        self.assertNotIn(self.expired, self.search())

    def test_home_page_search_and_match_sort(self):
        make_candidate("alice", skills=["React"])
        self.client.login(username="alice", password=PASSWORD)
        response = self.client.get(reverse("core:home"), {"sort": "match"})
        self.assertEqual(response.context["job_offers"][0], self.react)
        response = self.client.get(reverse("core:home"), {"q": "django"})
        self.assertEqual(response.context["total_results"], 1)
        self.assertTrue(response.context["has_filters"])

    def test_invalid_search_parameters_are_ignored(self):
        response = self.client.get(reverse("core:home"), {"salary_min": "abc"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_results"], 2)


class SavedJobAndAlertTests(TestCase):
    def setUp(self):
        self.recruiter = make_recruiter()
        self.offer = make_offer(self.recruiter, title="Python dev", skills=["Python"])
        self.candidate = make_candidate("alice")
        self.client.login(username="alice", password=PASSWORD)

    def test_toggle_saved_job(self):
        url = reverse("jobs:toggle_saved_job", args=[self.offer.pk])
        self.client.post(url, {"next": reverse("jobs:saved_jobs")})
        self.assertTrue(SavedJob.objects.exists())
        response = self.client.get(reverse("jobs:saved_jobs"))
        self.assertContains(response, "Python dev")
        response = self.client.post(url, {"next": "https://evil.example.com"})
        self.assertFalse(SavedJob.objects.exists())
        self.assertEqual(response.url, self.offer.get_absolute_url())

    def test_alert_crud(self):
        response = self.client.get(reverse("jobs:job_alert_create"), {"q": "python", "location": "Paris"})
        self.assertEqual(response.context["form"].initial["query"], "python")
        self.client.post(reverse("jobs:job_alert_create"), {"name": "Py", "query": "python", "is_active": True})
        alert = JobAlert.objects.get()
        self.client.post(reverse("jobs:job_alert_update", args=[alert.pk]), {"name": "Py2", "query": "python"})
        alert.refresh_from_db()
        self.assertEqual(alert.name, "Py2")
        self.assertFalse(alert.is_active)
        self.assertContains(self.client.get(reverse("jobs:job_alert_list")), "Py2")
        self.client.post(reverse("jobs:job_alert_delete", args=[alert.pk]))
        self.assertFalse(JobAlert.objects.exists())

    def test_alert_needs_a_criterion(self):
        response = self.client.post(reverse("jobs:job_alert_create"), {"name": "Empty", "is_active": True})
        self.assertTrue(response.context["form"].non_field_errors())

    def test_send_job_alerts(self):
        alert = JobAlert.objects.create(candidate=self.candidate.candidateprofile, name="Py", query="python")
        JobAlert.objects.filter(pk=alert.pk).update(created_at=timezone.now() - timedelta(days=1))
        JobOffer.objects.filter(pk=self.offer.pk).update(created_at=timezone.now())
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(send_job_alerts(), 1)
        self.assertEqual(Notification.objects.filter(kind=Notification.Kind.JOB_ALERT).count(), 1)
        self.assertEqual(len(mail.outbox), 1)
        # Second run: nothing new since last_sent_at.
        self.assertEqual(send_job_alerts(), 0)
