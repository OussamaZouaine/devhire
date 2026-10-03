from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from django import forms
from django.utils import timezone

from matching.fields import SkillListField

from .models import JobAlert, JobOffer


class JobOfferForm(forms.ModelForm):
    skills = SkillListField(label="Compétences requises")

    class Meta:
        model = JobOffer
        fields = (
            "title",
            "description",
            "location",
            "contract_type",
            "remote_policy",
            "experience_level",
            "skills",
            "salary_min",
            "salary_max",
            "deadline",
            "is_active",
        )
        widgets = {
            "description": forms.Textarea(attrs={"rows": 8}),
            "deadline": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.initial["skills"] = self.instance.skills.all()
        self.helper = FormHelper()
        self.helper.add_input(Submit("submit", "Enregistrer"))

    def clean_deadline(self):
        deadline = self.cleaned_data.get("deadline")
        changed = "deadline" in self.changed_data
        if deadline and changed and deadline < timezone.localdate():
            raise forms.ValidationError("La date limite ne peut pas être dans le passé.")
        return deadline

    def clean(self):
        cleaned = super().clean()
        salary_min, salary_max = cleaned.get("salary_min"), cleaned.get("salary_max")
        if salary_min and salary_max and salary_min > salary_max:
            self.add_error("salary_max", "Le salaire maximum doit être supérieur au minimum.")
        return cleaned


class JobSearchForm(forms.Form):
    """Validates the GET parameters of the search page."""

    q = forms.CharField(required=False, max_length=200)
    location = forms.CharField(required=False, max_length=100)
    contract_type = forms.ChoiceField(
        required=False,
        choices=[("", "Tous")] + JobOffer.ContractType.choices,
    )
    remote_policy = forms.ChoiceField(
        required=False,
        choices=[("", "Tous")] + JobOffer.RemotePolicy.choices,
    )
    experience_level = forms.ChoiceField(
        required=False,
        choices=[("", "Tous")] + JobOffer.ExperienceLevel.choices,
    )
    salary_min = forms.IntegerField(required=False, min_value=0)
    skill = forms.CharField(required=False, max_length=80)
    sort = forms.ChoiceField(
        required=False,
        choices=[
            ("", "Plus récentes"),
            ("relevance", "Pertinence"),
            ("salary", "Salaire"),
            ("match", "Compatibilité"),
        ],
    )

    def filters(self) -> dict:
        if not self.is_valid():
            return {}
        return {key: value for key, value in self.cleaned_data.items() if value not in ("", None)}


class JobAlertForm(forms.ModelForm):
    class Meta:
        model = JobAlert
        fields = ("name", "query", "location", "contract_type", "remote_policy", "salary_min", "is_active")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.add_input(Submit("submit", "Enregistrer l'alerte"))

    def clean(self):
        cleaned = super().clean()
        criteria = ("query", "location", "contract_type", "remote_policy", "salary_min")
        if not any(cleaned.get(field) for field in criteria):
            raise forms.ValidationError("Indiquez au moins un critère de recherche.")
        return cleaned
