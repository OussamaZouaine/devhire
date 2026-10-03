from datetime import timedelta

from django.db import models
from django.utils import timezone

from applications.models import Application
from jobs.models import JobOffer


class Quiz(models.Model):
    """Multiple-choice technical test attached to a job offer."""

    job_offer = models.OneToOneField(
        JobOffer,
        on_delete=models.CASCADE,
        related_name="quiz",
    )
    title = models.CharField("titre", max_length=150, default="Test technique")
    instructions = models.TextField("consignes", blank=True)
    time_limit_minutes = models.PositiveSmallIntegerField("durée (minutes)", default=15)
    is_active = models.BooleanField(
        "actif",
        default=True,
        help_text="Les candidats doivent passer le test après avoir postulé.",
    )

    # Extra time tolerated for network latency when submitting.
    GRACE_SECONDS = 30

    class Meta:
        verbose_name = "QCM"
        verbose_name_plural = "QCM"

    def __str__(self) -> str:
        return f"{self.title} — {self.job_offer.title}"

    @property
    def is_ready(self) -> bool:
        return self.is_active and self.questions.exists()


class Question(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="questions")
    text = models.TextField("question")
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "pk"]

    def __str__(self) -> str:
        return self.text[:60]


class Choice(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="choices")
    text = models.CharField("réponse", max_length=255)
    is_correct = models.BooleanField(default=False)

    class Meta:
        ordering = ["pk"]

    def __str__(self) -> str:
        return self.text


class QuizAttempt(models.Model):
    application = models.OneToOneField(
        Application,
        on_delete=models.CASCADE,
        related_name="quiz_attempt",
    )
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="attempts")
    started_at = models.DateTimeField(default=timezone.now)
    submitted_at = models.DateTimeField(blank=True, null=True)
    score = models.PositiveSmallIntegerField("score (%)", blank=True, null=True)
    correct_answers = models.PositiveSmallIntegerField(default=0)
    total_questions = models.PositiveSmallIntegerField(default=0)
    timed_out = models.BooleanField(default=False)

    def __str__(self) -> str:
        return f"Tentative {self.application} — {self.score}%"

    @property
    def deadline(self):
        return self.started_at + timedelta(minutes=self.quiz.time_limit_minutes)

    @property
    def is_submitted(self) -> bool:
        return self.submitted_at is not None

    @property
    def seconds_left(self) -> int:
        return max(0, int((self.deadline - timezone.now()).total_seconds()))

    def is_late(self, at=None) -> bool:
        at = at or timezone.now()
        return at > self.deadline + timedelta(seconds=Quiz.GRACE_SECONDS)


class AttemptAnswer(models.Model):
    attempt = models.ForeignKey(QuizAttempt, on_delete=models.CASCADE, related_name="answers")
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    choice = models.ForeignKey(Choice, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["attempt", "question"],
                name="one_answer_per_question",
            ),
        ]
