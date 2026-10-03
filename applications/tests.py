import json
from datetime import timedelta

from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from assessments.models import Choice, Question, Quiz
from core.factories import PASSWORD, make_application, make_candidate, make_company, make_offer, make_recruiter
from messaging.models import Notification

from .models import Application, Interview, RecruiterNote


class ApplyTests(TestCase):
    def setUp(self):
        self.recruiter = make_recruiter("rec")
        self.offer = make_offer(self.recruiter, skills=["Python"])
        self.candidate = make_candidate("alice", skills=["Python"])
        self.client.login(username="alice", password=PASSWORD)
        self.url = reverse("applications:apply_to_job", args=[self.offer.pk])

    def test_apply_records_history_score_and_notifies_company(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(self.url, {"cover_letter": "Motivée"})
        application = Application.objects.get()
        self.assertRedirects(response, reverse("applications:candidate_application_detail", args=[application.pk]))
        self.assertEqual(application.status, Application.Status.RECEIVED)
        self.assertGreater(application.match_score, 0)
        self.assertEqual(application.history.count(), 1)
        notification = Notification.objects.get(recipient=self.recruiter)
        self.assertEqual(notification.kind, Notification.Kind.APPLICATION_RECEIVED)
        self.assertEqual(len(mail.outbox), 1)

    def test_apply_redirects_to_quiz_when_offer_has_one(self):
        quiz = Quiz.objects.create(job_offer=self.offer)
        question = Question.objects.create(quiz=quiz, text="Q")
        Choice.objects.create(question=question, text="A", is_correct=True)
        response = self.client.post(self.url, {})
        application = Application.objects.get()
        self.assertRedirects(response, reverse("assessments:quiz_start", args=[application.pk]))

    def test_cannot_apply_to_expired_offer(self):
        self.offer.deadline = timezone.localdate() - timedelta(days=1)
        self.offer.save()
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_cannot_apply_twice_or_without_cv(self):
        make_application(self.candidate, self.offer)
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse("jobs:job_offer_detail", args=[self.offer.pk]))

        make_candidate("nocv", with_cv=False)
        self.client.login(username="nocv", password=PASSWORD)
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse("accounts:candidate_profile_update"))

    def test_recruiter_cannot_apply(self):
        self.client.login(username="rec", password=PASSWORD)
        self.assertEqual(self.client.get(self.url).status_code, 403)


class PipelineTests(TestCase):
    def setUp(self):
        self.company = make_company("Acme")
        self.recruiter = make_recruiter("rec", company=self.company)
        self.colleague = make_recruiter("colleague", company=self.company, admin=False)
        self.outsider = make_recruiter("outsider")
        self.offer = make_offer(self.recruiter, skills=["Python"])
        self.candidate = make_candidate("alice", skills=["Python"])
        self.application = make_application(self.candidate, self.offer)
        self.move_url = reverse("applications:update_application_status", args=[self.application.pk])

    def test_pipeline_board(self):
        self.client.login(username="colleague", password=PASSWORD)
        response = self.client.get(reverse("applications:pipeline", args=[self.offer.pk]))
        self.assertEqual(response.status_code, 200)
        received = dict((status, apps) for status, _, _, apps in response.context["columns"])["received"]
        self.assertEqual(received, [self.application])
        self.assertEqual(received[0].match.skill_score, 100)

    def test_outsider_cannot_access(self):
        self.client.login(username="outsider", password=PASSWORD)
        self.assertEqual(self.client.get(reverse("applications:pipeline", args=[self.offer.pk])).status_code, 404)
        self.assertEqual(
            self.client.get(reverse("applications:application_detail", args=[self.application.pk])).status_code, 404
        )
        self.assertEqual(self.client.post(self.move_url, {"status": "hired"}).status_code, 404)

    def test_move_via_json_records_history_and_notifies(self):
        self.client.login(username="colleague", password=PASSWORD)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                self.move_url, json.dumps({"status": "interview"}), content_type="application/json"
            )
        self.assertEqual(response.json(), {"ok": True, "changed": True, "status": "interview", "label": "Entretien"})
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, Application.Status.INTERVIEW)
        last = self.application.history.last()
        self.assertEqual((last.from_status, last.to_status, last.changed_by), ("received", "interview", self.colleague))
        self.assertTrue(Notification.objects.filter(recipient=self.candidate, kind="status_changed").exists())
        self.assertEqual(len(mail.outbox), 1)

    def test_invalid_status(self):
        self.client.login(username="rec", password=PASSWORD)
        response = self.client.post(self.move_url, json.dumps({"status": "withdrawn"}), content_type="application/json")
        self.assertEqual(response.status_code, 400)
        response = self.client.post(self.move_url, {"status": "nope"})
        self.assertRedirects(response, reverse("applications:application_detail", args=[self.application.pk]))

    def test_form_move_back_to_pipeline(self):
        self.client.login(username="rec", password=PASSWORD)
        response = self.client.post(self.move_url, {"status": "shortlisted", "next": "pipeline", "note": "Top"})
        self.assertRedirects(response, reverse("applications:pipeline", args=[self.offer.pk]))
        self.assertEqual(self.application.history.last().note, "Top")

    def test_withdrawn_application_cannot_be_moved(self):
        self.application.change_status(Application.Status.WITHDRAWN)
        self.client.login(username="rec", password=PASSWORD)
        response = self.client.post(self.move_url, json.dumps({"status": "hired"}), content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_change_status_helpers(self):
        self.assertFalse(self.application.change_status(Application.Status.RECEIVED))
        with self.assertRaises(ValueError):
            self.application.change_status("unknown")

    def test_detail_note_and_interview(self):
        self.client.login(username="rec", password=PASSWORD)
        response = self.client.get(reverse("applications:application_detail", args=[self.application.pk]))
        self.assertEqual(response.context["match"].skill_score, 100)

        self.client.post(reverse("applications:add_note", args=[self.application.pk]), {"content": "Solide"})
        self.assertEqual(RecruiterNote.objects.get().author, self.recruiter)
        self.client.post(reverse("applications:add_note", args=[self.application.pk]), {"content": ""})
        self.assertEqual(RecruiterNote.objects.count(), 1)

        when = (timezone.localtime() + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M")
        response = self.client.post(
            reverse("applications:schedule_interview", args=[self.application.pk]),
            {"scheduled_at": when, "duration_minutes": 45, "mode": "video", "location": "https://meet"},
        )
        self.assertRedirects(response, reverse("applications:application_detail", args=[self.application.pk]))
        interview = Interview.objects.get()
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, Application.Status.INTERVIEW)
        self.assertTrue(Notification.objects.filter(recipient=self.candidate, kind="interview").exists())

        ics = self.client.get(reverse("applications:interview_ics", args=[interview.pk]))
        self.assertEqual(ics["Content-Type"], "text/calendar; charset=utf-8")
        body = ics.content.decode()
        self.assertIn("BEGIN:VEVENT", body)
        self.assertIn("SUMMARY:Entretien", body)

        self.client.login(username="outsider", password=PASSWORD)
        self.assertEqual(self.client.get(reverse("applications:interview_ics", args=[interview.pk])).status_code, 403)

    def test_interview_in_the_past_is_rejected(self):
        self.client.login(username="rec", password=PASSWORD)
        when = (timezone.localtime() - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M")
        response = self.client.post(
            reverse("applications:schedule_interview", args=[self.application.pk]),
            {"scheduled_at": when, "duration_minutes": 45, "mode": "video"},
        )
        self.assertIn("scheduled_at", response.context["form"].errors)

    def test_cv_download_permissions(self):
        url = reverse("applications:download_cv", args=[self.application.pk])
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.login(username="colleague", password=PASSWORD)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.login(username="alice", password=PASSWORD)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.login(username="outsider", password=PASSWORD)
        self.assertEqual(self.client.get(url).status_code, 403)


class CandidateFollowUpTests(TestCase):
    def setUp(self):
        self.recruiter = make_recruiter("rec")
        self.offer = make_offer(self.recruiter)
        self.candidate = make_candidate("alice")
        self.application = make_application(self.candidate, self.offer)
        self.client.login(username="alice", password=PASSWORD)

    def test_detail_shows_progress(self):
        response = self.client.get(reverse("applications:candidate_application_detail", args=[self.application.pk]))
        self.assertEqual(response.context["current_step"], 0)

    def test_withdraw(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse("applications:withdraw", args=[self.application.pk]))
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, Application.Status.WITHDRAWN)
        self.assertTrue(Notification.objects.filter(recipient=self.recruiter).exists())
        self.client.post(reverse("applications:withdraw", args=[self.application.pk]))
        self.assertEqual(self.application.history.count(), 2)

    def test_other_candidate_cannot_see_application(self):
        make_candidate("bob")
        self.client.login(username="bob", password=PASSWORD)
        url = reverse("applications:candidate_application_detail", args=[self.application.pk])
        self.assertEqual(self.client.get(url).status_code, 404)
