from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from django import forms

from .models import JobOffer


class JobOfferForm(forms.ModelForm):
    class Meta:
        model = JobOffer
        fields = (
            "title",
            "description",
            "location",
            "contract_type",
            "keywords",
            "salary_min",
            "salary_max",
            "is_active",
        )
        widgets = {
            "description": forms.Textarea(attrs={"rows": 6}),
            "keywords": forms.TextInput(
                attrs={"placeholder": "python, django, remote, ..."}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.add_input(Submit("submit", "Enregistrer"))
