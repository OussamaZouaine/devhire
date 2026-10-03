from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.factories import PASSWORD, make_application, make_candidate, make_offer, make_recruiter

from .models import Question, Quiz, QuizAttempt


class QuizManagementTests(TestCase):
    def setUp(self):
        self.recruiter = make_recruiter("rec")
        self.offer = make_offer(self.recruiter)
        self.url = reverse("assessments:quiz_manage", args=[self.offer.pk])
        self.client.login(username="rec", password=PASSWORD)

    def test_add_question_creates_quiz(self):
        self.assertEqual(self.client.get(self.url).status_code, 200)
        response = self.client.post(
            self.url,
            {"text": "2 + 2 ?", "choice_1": "3", "choice_2": "4", "choice_3": "", "choice_4": "", "correct": "2"},
        )
        self.assertRedirects(response, self.url)
        question = Question.objects.get()
        self.assertEqual([c.text for c in question.choices.filter(is_correct=True)], ["4"])
        self.assertTrue(question.quiz.is_ready)

    def test_correct_answer_must_be_filled(self):
        response = self.client.post(self.url, {"text": "Q", "choice_1": "A", "choice_2": "B", "correct": "3"})
        self.assertIn("correct", response.context["question_form"].errors)

    def test_settings_and_delete_question(self):
        self.client.post(self.url, {"save_settings": "1", "title": "QCM", "time_limit_minutes": 5, "is_active": "on"})
        quiz = Quiz.objects.get()
        self.assertEqual(quiz.time_limit_minutes, 5)
        response = self.client.post(self.url, {"save_settings": "1", "title": "QCM", "time_limit_minutes": 0})
        self.assertIn("time_limit_minutes", response.context["settings_form"].errors)

        question = Question.objects.create(quiz=quiz, text="Q")
        self.client.post(reverse("assessments:delete_question", args=[question.pk]))
        self.assertFalse(Question.objects.exists())

    def test_other_company_cannot_manage(self):
        make_recruiter("other")
        self.client.login(username="other", password=PASSWORD)
        self.assertEqual(self.client.get(self.url).status_code, 404)


class TakeQuizTests(TestCase):
    def setUp(self):
        recruiter = make_recruiter("rec")
        self.offer = make_offer(recruiter)
        self.quiz = Quiz.objects.create(job_offer=self.offer, time_limit_minutes=10)
        self.questions = []
        for index in range(2):
            question = Question.objects.create(quiz=self.quiz, text=f"Q{index}")
            question.choices.create(text="good", is_correct=True)
            question.choices.create(text="bad", is_correct=False)
            self.questions.append(question)
        self.candidate = make_candidate("alice")
        self.application = make_application(self.candidate, self.offer)
        self.client.login(username="alice", password=PASSWORD)

    def answers(self, *texts):
        return {
            f"question_{question.pk}": question.choices.get(text=text).pk
            for question, text in zip(self.questions, texts, strict=False)
        }

    def start(self):
        start_url = reverse("assessments:quiz_start", args=[self.application.pk])
        self.assertEqual(self.client.get(start_url).status_code, 200)
        self.client.post(start_url)
        return reverse("assessments:quiz_take", args=[self.application.pk])

    def test_full_flow_scores_answers(self):
        take_url = self.start()
        self.assertEqual(self.client.get(take_url).status_code, 200)
        self.client.post(take_url, self.answers("good", "bad"))
        attempt = QuizAttempt.objects.get()
        self.assertEqual((attempt.score, attempt.correct_answers, attempt.total_questions), (50, 1, 2))
        self.assertFalse(attempt.timed_out)

        # A second submission is refused and the score is unchanged.
        self.client.post(take_url, self.answers("good", "good"))
        attempt.refresh_from_db()
        self.assertEqual(attempt.score, 50)
        self.assertRedirects(
            self.client.get(take_url), reverse("applications:candidate_application_detail", args=[self.application.pk])
        )

    def test_unanswered_questions_count_as_wrong(self):
        take_url = self.start()
        self.client.post(take_url, self.answers("good"))
        self.assertEqual(QuizAttempt.objects.get().score, 50)

    def test_late_submission_scores_zero(self):
        take_url = self.start()
        QuizAttempt.objects.update(started_at=timezone.now() - timedelta(minutes=20))
        self.client.post(take_url, self.answers("good", "good"))
        attempt = QuizAttempt.objects.get()
        self.assertTrue(attempt.timed_out)
        self.assertEqual(attempt.score, 0)

    def test_restart_redirects_to_existing_attempt(self):
        self.start()
        response = self.client.get(reverse("assessments:quiz_start", args=[self.application.pk]))
        self.assertRedirects(response, reverse("assessments:quiz_take", args=[self.application.pk]))

    def test_no_quiz(self):
        self.quiz.delete()
        response = self.client.get(reverse("assessments:quiz_start", args=[self.application.pk]))
        self.assertRedirects(response, reverse("applications:candidate_application_detail", args=[self.application.pk]))
