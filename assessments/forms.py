from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from django import forms

from .models import Choice, Question, Quiz

CHOICE_COUNT = 4


class QuizSettingsForm(forms.ModelForm):
    class Meta:
        model = Quiz
        fields = ("title", "instructions", "time_limit_minutes", "is_active")
        widgets = {"instructions": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.add_input(Submit("save_settings", "Enregistrer les paramètres"))

    def clean_time_limit_minutes(self):
        value = self.cleaned_data["time_limit_minutes"]
        if not 1 <= value <= 180:
            raise forms.ValidationError("La durée doit être comprise entre 1 et 180 minutes.")
        return value


class QuestionForm(forms.Form):
    """A question with up to 4 answers, exactly one of them correct."""

    text = forms.CharField(label="Question", widget=forms.Textarea(attrs={"rows": 2}))
    choice_1 = forms.CharField(label="Réponse 1", max_length=255)
    choice_2 = forms.CharField(label="Réponse 2", max_length=255)
    choice_3 = forms.CharField(label="Réponse 3", max_length=255, required=False)
    choice_4 = forms.CharField(label="Réponse 4", max_length=255, required=False)
    correct = forms.TypedChoiceField(
        label="Bonne réponse",
        choices=[(i, f"Réponse {i}") for i in range(1, CHOICE_COUNT + 1)],
        coerce=int,
    )

    def clean(self):
        cleaned = super().clean()
        correct = cleaned.get("correct")
        if correct and not cleaned.get(f"choice_{correct}"):
            self.add_error("correct", "La bonne réponse doit correspondre à une réponse remplie.")
        return cleaned

    def save(self, quiz: Quiz) -> Question:
        question = Question.objects.create(
            quiz=quiz,
            text=self.cleaned_data["text"],
            order=quiz.questions.count() + 1,
        )
        for index in range(1, CHOICE_COUNT + 1):
            text = self.cleaned_data.get(f"choice_{index}")
            if text:
                Choice.objects.create(
                    question=question,
                    text=text,
                    is_correct=index == self.cleaned_data["correct"],
                )
        return question


class TakeQuizForm(forms.Form):
    """One radio field per question; built dynamically from the quiz."""

    def __init__(self, *args, quiz: Quiz, **kwargs):
        super().__init__(*args, **kwargs)
        self.quiz = quiz
        self.questions = list(quiz.questions.prefetch_related("choices"))
        for question in self.questions:
            self.fields[f"question_{question.pk}"] = forms.ModelChoiceField(
                queryset=question.choices.all(),
                widget=forms.RadioSelect,
                empty_label=None,
                required=False,
                label=question.text,
            )

    def answers(self):
        """[(question, choice or None)] — unanswered questions count as wrong."""
        return [(question, self.cleaned_data.get(f"question_{question.pk}")) for question in self.questions]
