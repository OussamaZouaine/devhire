from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from accounts.mixins import CandidateRequiredMixin, RecruiterRequiredMixin
from applications.models import Application
from jobs.models import JobOffer

from .forms import QuestionForm, QuizSettingsForm, TakeQuizForm
from .models import Question, Quiz, QuizAttempt
from .services import grade_attempt


class QuizManageView(RecruiterRequiredMixin, View):
    """Create / edit the technical test of an offer."""

    template_name = "assessments/quiz_manage.html"

    def get_offer(self):
        return get_object_or_404(JobOffer, pk=self.kwargs["job_offer_id"], company=self.get_company())

    def render_page(self, offer, quiz, settings_form=None, question_form=None):
        return render(
            self.request,
            self.template_name,
            {
                "job_offer": offer,
                "quiz": quiz,
                "settings_form": settings_form or QuizSettingsForm(instance=quiz),
                "question_form": question_form or QuestionForm(),
                "questions": quiz.questions.prefetch_related("choices") if quiz.pk else [],
                "attempt_count": quiz.attempts.filter(submitted_at__isnull=False).count() if quiz.pk else 0,
            },
        )

    def get(self, request, job_offer_id):
        offer = self.get_offer()
        quiz = Quiz.objects.filter(job_offer=offer).first() or Quiz(job_offer=offer)
        return self.render_page(offer, quiz)

    def post(self, request, job_offer_id):
        offer = self.get_offer()
        quiz = Quiz.objects.filter(job_offer=offer).first() or Quiz(job_offer=offer)

        if "save_settings" in request.POST:
            form = QuizSettingsForm(request.POST, instance=quiz)
            if form.is_valid():
                form.save()
                messages.success(request, "Paramètres du test enregistrés.")
                return redirect("assessments:quiz_manage", job_offer_id=offer.pk)
            return self.render_page(offer, quiz, settings_form=form)

        form = QuestionForm(request.POST)
        if form.is_valid():
            if not quiz.pk:
                quiz.save()
            form.save(quiz)
            messages.success(request, "Question ajoutée.")
            return redirect("assessments:quiz_manage", job_offer_id=offer.pk)
        return self.render_page(offer, quiz, question_form=form)


class DeleteQuestionView(RecruiterRequiredMixin, View):
    def post(self, request, pk):
        question = get_object_or_404(
            Question.objects.select_related("quiz"),
            pk=pk,
            quiz__job_offer__company=self.get_company(),
        )
        offer_id = question.quiz.job_offer_id
        question.delete()
        messages.info(request, "Question supprimée.")
        return redirect("assessments:quiz_manage", job_offer_id=offer_id)


class CandidateQuizMixin(CandidateRequiredMixin):
    def get_application(self):
        application = get_object_or_404(
            Application.objects.select_related("job_offer__quiz"),
            pk=self.kwargs["application_id"],
            candidate=self.request.user.get_candidate_profile(),
        )
        quiz = getattr(application.job_offer, "quiz", None)
        if quiz is None or not quiz.is_ready:
            return application, None
        return application, quiz


class QuizStartView(CandidateQuizMixin, View):
    template_name = "assessments/quiz_start.html"

    def get(self, request, application_id):
        application, quiz = self.get_application()
        if quiz is None:
            messages.info(request, "Aucun test n'est associé à cette offre.")
            return redirect("applications:candidate_application_detail", pk=application.pk)
        attempt = QuizAttempt.objects.filter(application=application).first()
        if attempt:
            return redirect("assessments:quiz_take", application_id=application.pk)
        return render(
            request,
            self.template_name,
            {"application": application, "quiz": quiz, "question_count": quiz.questions.count()},
        )

    def post(self, request, application_id):
        application, quiz = self.get_application()
        if quiz is None or application.is_closed:
            return redirect("applications:candidate_application_detail", pk=application.pk)
        QuizAttempt.objects.get_or_create(application=application, defaults={"quiz": quiz})
        return redirect("assessments:quiz_take", application_id=application.pk)


class QuizTakeView(CandidateQuizMixin, View):
    template_name = "assessments/quiz_take.html"

    def get_attempt(self):
        application, quiz = self.get_application()
        attempt = get_object_or_404(QuizAttempt, application=application)
        return application, attempt

    def get(self, request, application_id):
        application, attempt = self.get_attempt()
        if attempt.is_submitted:
            return redirect("applications:candidate_application_detail", pk=application.pk)
        form = TakeQuizForm(quiz=attempt.quiz)
        return render(request, self.template_name, {"application": application, "attempt": attempt, "form": form})

    def post(self, request, application_id):
        application, attempt = self.get_attempt()
        if attempt.is_submitted:
            messages.error(request, "Vous avez déjà soumis ce test.")
            return redirect("applications:candidate_application_detail", pk=application.pk)
        form = TakeQuizForm(request.POST, quiz=attempt.quiz)
        form.is_valid()
        attempt = grade_attempt(attempt, form.answers())
        if attempt.timed_out:
            messages.warning(request, "Temps écoulé : le test a été soumis hors délai.")
        else:
            messages.success(
                request, f"Test soumis : {attempt.correct_answers}/{attempt.total_questions} bonnes réponses."
            )
        return redirect("applications:candidate_application_detail", pk=application.pk)
