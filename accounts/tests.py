from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.factories import PASSWORD, make_candidate, make_company, make_offer, make_recruiter, pdf_file

from .models import CandidateProfile, Company, CompanyInvitation, RecruiterProfile, User


class SignUpTests(TestCase):
    def test_candidate_signup_logs_in_and_creates_profile(self):
        response = self.client.post(
            reverse("accounts:signup_candidate"),
            {
                "username": "newcandidate",
                "email": "new@test.com",
                "password1": PASSWORD,
                "password2": PASSWORD,
                "location": "Lyon",
            },
        )
        self.assertRedirects(response, reverse("accounts:candidate_profile_update"))
        user = User.objects.get(username="newcandidate")
        self.assertEqual(user.role, User.Role.CANDIDATE)
        self.assertEqual(user.candidateprofile.location, "Lyon")
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_recruiter_signup_creates_company_as_admin(self):
        response = self.client.post(
            reverse("accounts:signup_recruiter"),
            {
                "username": "newrecruiter",
                "email": "rec@test.com",
                "password1": PASSWORD,
                "password2": PASSWORD,
                "company_name": "Acme",
            },
        )
        self.assertRedirects(response, reverse("jobs:recruiter_dashboard"))
        profile = RecruiterProfile.objects.get(user__username="newrecruiter")
        self.assertEqual(profile.company.name, "Acme")
        self.assertEqual(profile.company.slug, "acme")
        self.assertTrue(profile.is_company_admin)
        self.assertEqual(Company.objects.count(), 1)

    def test_company_slugs_are_unique(self):
        first = Company.objects.create(name="Acme")
        second = Company.objects.create(name="Acme")
        self.assertNotEqual(first.slug, second.slug)

    def test_login_redirects_by_role(self):
        make_recruiter("rec")
        response = self.client.post(reverse("accounts:login"), {"username": "rec", "password": PASSWORD})
        self.assertRedirects(response, reverse("jobs:recruiter_dashboard"))

    def test_password_reset_sends_email(self):
        make_candidate("forgetful")
        response = self.client.post(reverse("accounts:password_reset"), {"email": "forgetful@test.com"})
        self.assertRedirects(response, reverse("accounts:password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/compte/mot-de-passe/reinitialiser/", mail.outbox[0].body)


class CandidateProfileTests(TestCase):
    def setUp(self):
        self.user = make_candidate("alice", with_cv=False)
        self.client.login(username="alice", password=PASSWORD)

    def test_uploading_cv_extracts_text_and_suggests_skills(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse("accounts:candidate_profile_update"),
                {
                    "headline": "Dev",
                    "years_of_experience": 2,
                    "cv": pdf_file(text="Python Django Kubernetes"),
                    "skills": "Python",
                },
            )
        self.assertEqual(response.status_code, 302)
        profile = CandidateProfile.objects.get(user=self.user)
        self.assertIn("Kubernetes", profile.cv_text)
        self.assertEqual(profile.skill_names, ["Python"])

        response = self.client.get(reverse("accounts:candidate_profile_update"))
        self.assertEqual(response.context["suggested_skills"], ["Django", "Kubernetes"])

        self.client.post(reverse("accounts:add_suggested_skills"), {"skills": ["Django", "Hacking"]})
        self.assertEqual(sorted(profile.skill_names), ["Django", "Python"])

    def test_cv_must_be_pdf(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        response = self.client.post(
            reverse("accounts:candidate_profile_update"),
            {"years_of_experience": 0, "cv": SimpleUploadedFile("cv.txt", b"hello", content_type="text/plain")},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors["cv"])

    def test_background_formsets(self):
        url = reverse("accounts:candidate_background")
        self.assertEqual(self.client.get(url).status_code, 200)
        data = {}
        for prefix in ("experiences", "educations", "languages"):
            data.update({f"{prefix}-TOTAL_FORMS": "1", f"{prefix}-INITIAL_FORMS": "0"})
        data.update(
            {
                "experiences-0-title": "Développeuse",
                "experiences-0-company": "Acme",
                "experiences-0-start_date": "2022-01-01",
                "educations-0-school": "EPITA",
                "educations-0-degree": "Ingénieur",
                "educations-0-start_year": "2017",
                "languages-0-name": "Anglais",
                "languages-0-level": "C1",
            }
        )
        response = self.client.post(url, data)
        self.assertRedirects(response, url)
        profile = self.user.get_candidate_profile()
        self.assertEqual(profile.experiences.count(), 1)
        self.assertEqual(profile.educations.count(), 1)
        self.assertEqual(profile.languages.count(), 1)

    def test_background_rejects_end_before_start(self):
        data = {}
        for prefix in ("experiences", "educations", "languages"):
            data.update({f"{prefix}-TOTAL_FORMS": "1", f"{prefix}-INITIAL_FORMS": "0"})
        data.update(
            {
                "experiences-0-title": "Dev",
                "experiences-0-company": "Acme",
                "experiences-0-start_date": "2022-01-01",
                "experiences-0-end_date": "2021-01-01",
            }
        )
        response = self.client.post(reverse("accounts:candidate_background"), data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.user.get_candidate_profile().experiences.exists())

    def test_completion_percent(self):
        profile = self.user.get_candidate_profile()
        self.assertEqual(profile.completion_percent, 0)
        profile.headline = "Dev"
        profile.location = "Paris"
        self.assertEqual(profile.completion_percent, 29)


class CompanyTests(TestCase):
    def setUp(self):
        self.company = make_company("Acme")
        self.admin = make_recruiter("admin", company=self.company, admin=True)
        self.member = make_recruiter("member", company=self.company, admin=False)

    def test_only_admin_can_edit_company(self):
        self.client.login(username="member", password=PASSWORD)
        self.assertEqual(self.client.get(reverse("accounts:company_update")).status_code, 403)
        self.client.login(username="admin", password=PASSWORD)
        response = self.client.post(
            reverse("accounts:company_update"),
            {"name": "Acme Corp", "location": "Paris", "website": "https://acme.test", "description": "Hello"},
        )
        self.assertRedirects(response, reverse("accounts:company_update"))
        self.company.refresh_from_db()
        self.assertEqual(self.company.name, "Acme Corp")

    def test_public_company_page_lists_open_offers(self):
        make_offer(self.admin, title="Visible")
        make_offer(self.admin, title="Hidden", is_active=False)
        response = self.client.get(self.company.get_absolute_url())
        self.assertContains(response, "Visible")
        self.assertNotContains(response, "Hidden")
        self.assertContains(self.client.get(reverse("accounts:company_list")), "Acme")

    def test_member_cannot_invite(self):
        self.client.login(username="member", password=PASSWORD)
        self.client.post(reverse("accounts:company_team"), {"email": "x@test.com", "role": "member"})
        self.assertFalse(CompanyInvitation.objects.exists())

    def test_invitation_for_new_user(self):
        self.client.login(username="admin", password=PASSWORD)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse("accounts:company_team"), {"email": "new@test.com", "role": "member"})
        invitation = CompanyInvitation.objects.get()
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(str(invitation.token), mail.outbox[0].body)

        self.client.logout()
        url = invitation.get_absolute_url()
        self.assertNotIn("company_name", self.client.get(url).context["form"].fields)
        response = self.client.post(
            url,
            {"username": "newbie", "email": "new@test.com", "password1": PASSWORD, "password2": PASSWORD},
        )
        self.assertRedirects(response, reverse("jobs:recruiter_dashboard"))
        profile = RecruiterProfile.objects.get(user__username="newbie")
        self.assertEqual(profile.company, self.company)
        self.assertFalse(profile.is_company_admin)
        invitation.refresh_from_db()
        self.assertIsNotNone(invitation.accepted_at)
        self.assertEqual(self.client.get(url).status_code, 302)

    def test_existing_recruiter_joins_and_keeps_offers(self):
        other = make_recruiter("other")
        old_company = other.get_recruiter_profile().company
        offer = make_offer(other)
        invitation = CompanyInvitation.objects.create(
            company=self.company, email="other@test.com", invited_by=self.admin
        )
        self.client.login(username="other", password=PASSWORD)
        self.client.get(invitation.get_absolute_url())
        other.recruiterprofile.refresh_from_db()
        self.assertEqual(other.recruiterprofile.company, self.company)
        offer.refresh_from_db()
        self.assertEqual(offer.company, self.company)
        self.assertFalse(Company.objects.filter(pk=old_company.pk).exists())

    def test_invitation_rejects_other_account(self):
        invitation = CompanyInvitation.objects.create(company=self.company, email="someone@test.com")
        make_candidate("cand")
        self.client.login(username="cand", password=PASSWORD)
        self.client.get(invitation.get_absolute_url())
        invitation.refresh_from_db()
        self.assertIsNone(invitation.accepted_at)

    def test_expired_invitation(self):
        invitation = CompanyInvitation.objects.create(company=self.company, email="late@test.com")
        CompanyInvitation.objects.filter(pk=invitation.pk).update(
            created_at=timezone.now() - timezone.timedelta(days=8)
        )
        response = self.client.get(invitation.get_absolute_url())
        self.assertRedirects(response, reverse("core:home"))

    def test_admin_can_remove_member_and_cancel_invitation(self):
        invitation = CompanyInvitation.objects.create(company=self.company, email="x@test.com")
        self.client.login(username="admin", password=PASSWORD)
        self.client.post(reverse("accounts:cancel_invitation", args=[invitation.pk]))
        self.assertFalse(CompanyInvitation.objects.exists())

        member_profile = self.member.get_recruiter_profile()
        self.client.post(reverse("accounts:remove_member", args=[member_profile.pk]))
        member_profile.refresh_from_db()
        self.assertNotEqual(member_profile.company, self.company)
        self.assertTrue(member_profile.is_company_admin)

        admin_profile = self.admin.get_recruiter_profile()
        self.client.post(reverse("accounts:remove_member", args=[admin_profile.pk]))
        admin_profile.refresh_from_db()
        self.assertEqual(admin_profile.company, self.company)

    def test_recruiter_account_update(self):
        self.client.login(username="member", password=PASSWORD)
        self.client.post(
            reverse("accounts:recruiter_account"),
            {"first_name": "Karim", "last_name": "H", "email": "member@test.com", "job_title": "CTO"},
        )
        self.member.refresh_from_db()
        self.assertEqual(self.member.first_name, "Karim")
        self.assertEqual(self.member.recruiterprofile.job_title, "CTO")


class CandidatePublicProfileTests(TestCase):
    def test_only_recruiters_can_view(self):
        candidate = make_candidate("alice")
        url = reverse("accounts:candidate_public_profile", args=[candidate.candidateprofile.pk])
        make_recruiter("rec")
        self.client.login(username="rec", password=PASSWORD)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.login(username="alice", password=PASSWORD)
        self.assertEqual(self.client.get(url).status_code, 403)
