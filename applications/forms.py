from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from django import forms

from .models import Application


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
