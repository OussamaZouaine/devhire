from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import User
from applications.models import Application
from jobs.models import JobOffer


class DevHirePlatformTests(TestCase):
    def setUp(self):
        self.client = Client()

        self.recruiter = User.objects.create_user(
            username="recruiter_a",
            email="recruiter_a@test.com",
            password="TestPass123!",
            role=User.Role.RECRUITER,
        )
        self.recruiter_profile = self.recruiter.get_recruiter_profile()
        self.recruiter_profile.company_name = "Acme Corp"
        self.recruiter_profile.save()

        self.other_recruiter = User.objects.create_user(
            username="recruiter_b",
            email="recruiter_b@test.com",
            password="TestPass123!",
            role=User.Role.RECRUITER,
        )
        self.other_recruiter_profile = self.other_recruiter.get_recruiter_profile()
        self.other_recruiter_profile.company_name = "Beta Inc"
        self.other_recruiter_profile.save()

        self.candidate = User.objects.create_user(
            username="candidate_a",
            email="candidate_a@test.com",
            password="TestPass123!",
            role=User.Role.CANDIDATE,
        )
        self.candidate_profile = self.candidate.get_candidate_profile()
        self.candidate_profile.cv = SimpleUploadedFile(
            "cv.pdf",
            b"%PDF-1.4 test content",
            content_type="application/pdf",
        )
        self.candidate_profile.save()

        self.offer = JobOffer.objects.create(
            recruiter=self.recruiter_profile,
            title="Développeur Django",
            description="Poste backend",
            location="Paris",
            contract_type=JobOffer.ContractType.CDI,
            keywords="django, python",
        )

    def test_recruiter_can_create_job_offer(self):
        self.client.login(username="recruiter_a", password="TestPass123!")
        response = self.client.post(
            reverse("jobs:job_offer_create"),
            {
                "title": "Dev Frontend",
                "description": "React developer needed",
                "location": "Lyon",
                "contract_type": "CDD",
                "keywords": "react",
                "is_active": True,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            JobOffer.objects.filter(
                title="Dev Frontend",
                recruiter=self.recruiter_profile,
            ).exists()
        )

    def test_candidate_can_apply_to_job_offer(self):
        self.client.login(username="candidate_a", password="TestPass123!")
        response = self.client.post(
            reverse("applications:apply_to_job", kwargs={"job_offer_id": self.offer.pk}),
            {"cover_letter": "Je suis motivé."},
        )
        self.assertEqual(response.status_code, 302)
        application = Application.objects.get(
            candidate=self.candidate_profile,
            job_offer=self.offer,
        )
        self.assertEqual(application.status, Application.Status.PENDING)
        self.assertEqual(application.cover_letter, "Je suis motivé.")

    def test_recruiter_can_update_application_status(self):
        application = Application.objects.create(
            candidate=self.candidate_profile,
            job_offer=self.offer,
        )
        self.client.login(username="recruiter_a", password="TestPass123!")
        response = self.client.post(
            reverse("applications:update_application_status", kwargs={"pk": application.pk}),
            {"action": "accept"},
        )
        self.assertEqual(response.status_code, 302)
        application.refresh_from_db()
        self.assertEqual(application.status, Application.Status.ACCEPTED)

    def test_candidate_cannot_update_another_recruiters_job_offer(self):
        self.client.login(username="candidate_a", password="TestPass123!")
        response = self.client.get(
            reverse("jobs:job_offer_update", kwargs={"pk": self.offer.pk}),
        )
        self.assertEqual(response.status_code, 403)

    def test_other_recruiter_cannot_update_foreign_job_offer(self):
        self.client.login(username="recruiter_b", password="TestPass123!")
        response = self.client.get(
            reverse("jobs:job_offer_update", kwargs={"pk": self.offer.pk}),
        )
        self.assertEqual(response.status_code, 404)

    def test_direct_cv_media_access_is_blocked(self):
        response = self.client.get("/media/cvs/user_1/cv.pdf")
        self.assertEqual(response.status_code, 403)

    def test_candidate_can_view_inactive_offer_they_applied_to(self):
        Application.objects.create(
            candidate=self.candidate_profile,
            job_offer=self.offer,
        )
        self.offer.is_active = False
        self.offer.save()

        self.client.login(username="candidate_a", password="TestPass123!")
        response = self.client.get(
            reverse("jobs:job_offer_detail", kwargs={"pk": self.offer.pk}),
        )
        self.assertEqual(response.status_code, 200)

    def test_apply_form_redirects_when_cv_missing(self):
        self.candidate_profile.cv = None
        self.candidate_profile.save()

        self.client.login(username="candidate_a", password="TestPass123!")
        response = self.client.get(
            reverse("applications:apply_to_job", kwargs={"job_offer_id": self.offer.pk}),
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("accounts:candidate_profile_update"))

    def test_apply_form_redirects_when_already_applied(self):
        Application.objects.create(
            candidate=self.candidate_profile,
            job_offer=self.offer,
        )

        self.client.login(username="candidate_a", password="TestPass123!")
        response = self.client.get(
            reverse("applications:apply_to_job", kwargs={"job_offer_id": self.offer.pk}),
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            reverse("jobs:job_offer_detail", kwargs={"pk": self.offer.pk}),
        )
