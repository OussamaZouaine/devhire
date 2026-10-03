from django.urls import reverse
from rest_framework.test import APITestCase

from applications.models import Application
from core.factories import PASSWORD, make_application, make_candidate, make_offer, make_recruiter
from jobs.models import JobOffer
from messaging.models import Notification


class ApiTests(APITestCase):
    def setUp(self):
        self.recruiter = make_recruiter("rec")
        self.offer = make_offer(self.recruiter, title="Dev Django", skills=["Python", "Django"])
        self.candidate = make_candidate("alice", skills=["Python"])

    def authenticate(self, username):
        response = self.client.post(reverse("api:token_obtain_pair"), {"username": username, "password": PASSWORD})
        self.assertEqual(response.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

    def test_public_offer_list_and_filters(self):
        make_offer(self.recruiter, title="Inactive", is_active=False)
        response = self.client.get(reverse("api:joboffer-list"))
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["skills"], ["Django", "Python"])
        response = self.client.get(reverse("api:joboffer-list"), {"q": "react"})
        self.assertEqual(response.data["count"], 0)
        response = self.client.get(reverse("api:joboffer-list"), {"salary_min": "x"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.get(reverse("api:joboffer-detail", args=[self.offer.pk])).status_code, 200)

    def test_anonymous_cannot_write(self):
        response = self.client.post(reverse("api:joboffer-list"), {"title": "x"})
        self.assertEqual(response.status_code, 401)

    def test_recruiter_creates_and_updates_offer(self):
        self.authenticate("rec")
        response = self.client.post(
            reverse("api:joboffer-list"),
            {"title": "API offer", "description": "d", "location": "Lyon", "skills": ["Go", "Docker"]},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        offer = JobOffer.objects.get(title="API offer")
        self.assertEqual(offer.company, self.recruiter.get_recruiter_profile().company)
        response = self.client.patch(
            reverse("api:joboffer-detail", args=[offer.pk]),
            {"skills": ["Go"], "salary_min": 10, "salary_max": 5},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        response = self.client.patch(reverse("api:joboffer-detail", args=[offer.pk]), {"skills": ["Go"]}, format="json")
        self.assertEqual(response.data["skills"], ["Go"])
        self.assertEqual(self.client.get(reverse("api:joboffer-mine")).data["count"], 2)

    def test_other_recruiter_cannot_update(self):
        make_recruiter("other")
        self.authenticate("other")
        response = self.client.patch(
            reverse("api:joboffer-detail", args=[self.offer.pk]), {"title": "x"}, format="json"
        )
        self.assertEqual(response.status_code, 403)

    def test_candidate_apply_flow(self):
        self.authenticate("alice")
        response = self.client.post(reverse("api:application-list"), {"job_offer": self.offer.pk, "cover_letter": "Hi"})
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["status"], "received")
        response = self.client.post(reverse("api:application-list"), {"job_offer": self.offer.pk})
        self.assertEqual(response.status_code, 400)
        application_id = Application.objects.get().pk
        self.assertEqual(self.client.get(reverse("api:application-list")).data["count"], 1)

        response = self.client.post(reverse("api:application-withdraw", args=[application_id]))
        self.assertEqual(response.data["status"], "withdrawn")
        response = self.client.post(reverse("api:application-withdraw", args=[application_id]))
        self.assertEqual(response.status_code, 400)

    def test_candidate_without_cv_cannot_apply(self):
        make_candidate("nocv", with_cv=False)
        self.authenticate("nocv")
        response = self.client.post(reverse("api:application-list"), {"job_offer": self.offer.pk})
        self.assertEqual(response.status_code, 400)

    def test_recruiter_changes_status(self):
        application = make_application(self.candidate, self.offer)
        self.authenticate("rec")
        self.assertEqual(
            self.client.post(reverse("api:application-list"), {"job_offer": self.offer.pk}).status_code, 403
        )
        url = reverse("api:application-change-status", args=[application.pk])
        response = self.client.post(url, {"status": "interview", "note": "Go"})
        self.assertEqual(response.data["status"], "interview")
        self.assertEqual(self.client.post(url, {"status": "nope"}).status_code, 400)
        response = self.client.get(reverse("api:application-list"), {"status": "interview"})
        self.assertEqual(response.data["count"], 1)

    def test_candidate_cannot_change_status(self):
        application = make_application(self.candidate, self.offer)
        self.authenticate("alice")
        response = self.client.post(
            reverse("api:application-change-status", args=[application.pk]), {"status": "hired"}
        )
        self.assertEqual(response.status_code, 403)

    def test_recommendations_match_and_profile(self):
        self.authenticate("alice")
        response = self.client.get(reverse("api:joboffer-recommended"))
        self.assertEqual(response.data[0]["offer"]["id"], self.offer.pk)
        response = self.client.get(reverse("api:joboffer-match-score", args=[self.offer.pk]))
        self.assertEqual(response.data["skill_score"], 50)
        self.assertEqual(response.data["missing_skills"], ["Django"])

        response = self.client.get(reverse("api:me"))
        self.assertEqual(response.data["candidate_profile"]["skills"], ["Python"])
        response = self.client.patch(reverse("api:candidate_profile"), {"skills": ["Python", "Django"]}, format="json")
        self.assertEqual(sorted(response.data["skills"]), ["Django", "Python"])

    def test_recruiter_me_and_skills(self):
        self.authenticate("rec")
        self.assertIn("company", self.client.get(reverse("api:me")).data)
        response = self.client.get(reverse("api:skill-list"), {"q": "pyt"})
        self.assertEqual([skill["name"] for skill in response.data], ["Python"])
        company = self.recruiter.get_recruiter_profile().company
        self.assertEqual(self.client.get(reverse("api:company-detail", args=[company.slug])).status_code, 200)

    def test_notifications(self):
        Notification.objects.create(recipient=self.candidate, kind="message", title="A")
        other = Notification.objects.create(recipient=self.candidate, kind="message", title="B")
        self.authenticate("alice")
        self.assertEqual(self.client.get(reverse("api:notification-list"), {"unread": "1"}).data["count"], 2)
        self.client.post(reverse("api:notification-read", args=[other.pk]))
        self.assertEqual(self.client.get(reverse("api:notification-list"), {"unread": "true"}).data["count"], 1)
        self.client.post(reverse("api:notification-read-all"))
        self.assertEqual(self.client.get(reverse("api:notification-list"), {"unread": "1"}).data["count"], 0)

    def test_docs_and_schema(self):
        self.assertEqual(self.client.get(reverse("api:swagger")).status_code, 200)
        self.assertEqual(self.client.get(reverse("api:schema")).status_code, 200)
