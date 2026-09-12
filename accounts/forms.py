from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import CandidateProfile, RecruiterProfile, User
from .validators import validate_file_max_size, validate_pdf_file


class CandidateProfileForm(forms.ModelForm):
    class Meta:
        model = CandidateProfile
        fields = ("cv", "phone", "bio", "skills", "location")
        widgets = {
            "bio": forms.Textarea(attrs={"rows": 4}),
            "skills": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.fields["cv"].help_text = "Format PDF uniquement, taille max. 5 Mo."

    def clean_cv(self):
        cv = self.cleaned_data.get("cv")
        if cv:
            validate_pdf_file(cv)
            validate_file_max_size(cv)
        return cv


class CandidateSignUpForm(UserCreationForm):
    phone = forms.CharField(max_length=20, required=False, label="Téléphone")
    location = forms.CharField(max_length=100, required=False, label="Localisation")

    class Meta:
        model = User
        fields = ("username", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.add_input(Submit("submit", "S'inscrire"))

    def save(self, commit: bool = True) -> User:
        user = super().save(commit=False)
        user.role = User.Role.CANDIDATE
        if commit:
            user.save()
            profile = user.get_candidate_profile()
            profile.phone = self.cleaned_data.get("phone", "")
            profile.location = self.cleaned_data.get("location", "")
            profile.save()
        return user


class RecruiterSignUpForm(UserCreationForm):
    company_name = forms.CharField(max_length=200, label="Nom de l'entreprise")

    class Meta:
        model = User
        fields = ("username", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.add_input(Submit("submit", "S'inscrire"))

    def save(self, commit: bool = True) -> User:
        user = super().save(commit=False)
        user.role = User.Role.RECRUITER
        if commit:
            user.save()
            profile = user.get_recruiter_profile()
            profile.company_name = self.cleaned_data["company_name"]
            profile.save()
        return user
