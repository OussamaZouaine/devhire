from django.db import transaction
from django.utils import timezone

from .models import AttemptAnswer, QuizAttempt


@transaction.atomic
def grade_attempt(attempt: QuizAttempt, answers) -> QuizAttempt:
    """
    Store the answers and compute the score.
    A submission received after the time limit (+ grace period) scores 0.
    """
    now = timezone.now()
    total = len(answers)
    correct = 0
    for question, choice in answers:
        if choice is None:
            continue
        AttemptAnswer.objects.create(attempt=attempt, question=question, choice=choice)
        if choice.is_correct and choice.question_id == question.pk:
            correct += 1

    attempt.submitted_at = now
    attempt.total_questions = total
    attempt.timed_out = attempt.is_late(now)
    attempt.correct_answers = 0 if attempt.timed_out else correct
    attempt.score = 0 if attempt.timed_out or not total else round(100 * correct / total)
    attempt.save()
    return attempt
