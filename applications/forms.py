from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from django import forms
from django.utils import timezone

from .models import Application, Interview, RecruiterNote


class ApplicationForm(forms.ModelForm):
    class Meta:
        model = Application
        fields = ("cover_letter",)
        widgets = {
            "cover_letter": forms.Textarea(
                attrs={
                    "rows": 5,
                    "placeholder": "Présentez-vous brièvement (optionnel)...",
                }
            ),
        }
        labels = {
            "cover_letter": "Lettre de motivation",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.add_input(Submit("submit", "Envoyer ma candidature"))


class StatusChangeForm(forms.Form):
    status = forms.ChoiceField(
        choices=[(s.value, s.label) for s in Application.PIPELINE],
        label="Nouveau statut",
        widget=forms.Select(attrs={"class": "form-select form-select-sm"}),
    )
    note = forms.CharField(max_length=255, required=False, label="Commentaire (optionnel)")


class RecruiterNoteForm(forms.ModelForm):
    class Meta:
        model = RecruiterNote
        fields = ("content",)
        widgets = {
            "content": forms.Textarea(
                attrs={
                    "rows": 3,
                    "class": "form-control",
                    "placeholder": "Note privée, visible uniquement par votre équipe",
                }
            )
        }
        labels = {"content": ""}


class InterviewForm(forms.ModelForm):
    class Meta:
        model = Interview
        fields = ("scheduled_at", "duration_minutes", "mode", "location", "notes")
        widgets = {
            "scheduled_at": forms.DateTimeInput(
                attrs={"type": "datetime-local"},
                format="%Y-%m-%dT%H:%M",
            ),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["scheduled_at"].input_formats = ["%Y-%m-%dT%H:%M"]
        self.helper = FormHelper()
        self.helper.add_input(Submit("submit", "Planifier l'entretien"))

    def clean_scheduled_at(self):
        scheduled_at = self.cleaned_data["scheduled_at"]
        if scheduled_at < timezone.now():
            raise forms.ValidationError("L'entretien doit être planifié dans le futur.")
        return scheduled_at

    def clean_duration_minutes(self):
        duration = self.cleaned_data["duration_minutes"]
        if not 10 <= duration <= 480:
            raise forms.ValidationError("La durée doit être comprise entre 10 et 480 minutes.")
        return duration
