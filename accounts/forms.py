from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.db import transaction

from matching.fields import SkillListField

from .models import (
    CandidateProfile,
    Company,
    CompanyInvitation,
    Education,
    Experience,
    Language,
    RecruiterProfile,
    User,
)
from .validators import validate_file_max_size, validate_image_file, validate_pdf_file


class CandidateProfileForm(forms.ModelForm):
    skills = SkillListField(label="Compétences")

    class Meta:
        model = CandidateProfile
        fields = (
            "headline",
            "years_of_experience",
            "cv",
            "phone",
            "location",
            "bio",
            "skills",
        )
        widgets = {
            "bio": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.fields["cv"].help_text = (
            "Format PDF uniquement, taille max. 5 Mo. Les compétences détectées dans votre CV vous seront suggérées."
        )
        if self.instance.pk:
            self.initial["skills"] = self.instance.skills.all()

    def clean_cv(self):
        cv = self.cleaned_data.get("cv")
        if cv and hasattr(cv, "content_type"):
            validate_pdf_file(cv)
            validate_file_max_size(cv)
        return cv


class BootstrapWidgetsMixin:
    """Add Bootstrap classes to widgets rendered manually (formsets)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                css = "form-check-input"
            elif isinstance(widget, forms.Select):
                css = "form-select form-select-sm"
            else:
                css = "form-control form-control-sm"
            widget.attrs["class"] = f"{widget.attrs.get('class', '')} {css}".strip()


class ExperienceForm(BootstrapWidgetsMixin, forms.ModelForm):
    class Meta:
        model = Experience
        fields = ("title", "company", "start_date", "end_date", "description")
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "end_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "description": forms.Textarea(attrs={"rows": 2}),
        }

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("start_date"), cleaned.get("end_date")
        if start and end and end < start:
            self.add_error("end_date", "La date de fin doit être après la date de début.")
        return cleaned


class EducationForm(BootstrapWidgetsMixin, forms.ModelForm):
    class Meta:
        model = Education
        fields = ("school", "degree", "field_of_study", "start_year", "end_year")

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("start_year"), cleaned.get("end_year")
        if start and end and end < start:
            self.add_error("end_year", "L'année de fin doit être après l'année de début.")
        return cleaned


class LanguageForm(BootstrapWidgetsMixin, forms.ModelForm):
    class Meta:
        model = Language
        fields = ("name", "level")


ExperienceFormSet = forms.inlineformset_factory(
    CandidateProfile, Experience, form=ExperienceForm, extra=1, can_delete=True
)
EducationFormSet = forms.inlineformset_factory(
    CandidateProfile, Education, form=EducationForm, extra=1, can_delete=True
)
LanguageFormSet = forms.inlineformset_factory(CandidateProfile, Language, form=LanguageForm, extra=1, can_delete=True)


class CandidateSignUpForm(UserCreationForm):
    phone = forms.CharField(max_length=20, required=False, label="Téléphone")
    location = forms.CharField(max_length=100, required=False, label="Localisation")

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].required = True
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
    """Recruiter sign-up. Creates the company unless the user joins via an invitation."""

    company_name = forms.CharField(max_length=200, label="Nom de l'entreprise")

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email")

    def __init__(self, *args, invitation: CompanyInvitation | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.invitation = invitation
        self.fields["email"].required = True
        if invitation:
            del self.fields["company_name"]
            self.fields["email"].initial = invitation.email
        self.helper = FormHelper()
        self.helper.add_input(Submit("submit", "S'inscrire"))

    @transaction.atomic
    def save(self, commit: bool = True) -> User:
        user = super().save(commit=False)
        user.role = User.Role.RECRUITER
        if commit:
            if self.invitation:
                company = self.invitation.company
                company_role = self.invitation.role
            else:
                company = Company.objects.create(name=self.cleaned_data["company_name"])
                company_role = RecruiterProfile.CompanyRole.ADMIN
            # Set before save so the post_save signal does not create a placeholder company.
            user._pending_company = (company, company_role)
            user.save()
        return user


class CompanyForm(forms.ModelForm):
    class Meta:
        model = Company
        fields = ("name", "logo", "location", "website", "description")
        widgets = {"description": forms.Textarea(attrs={"rows": 5})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False

    def clean_logo(self):
        logo = self.cleaned_data.get("logo")
        if logo and hasattr(logo, "content_type"):
            validate_image_file(logo)
        return logo


class RecruiterAccountForm(forms.ModelForm):
    job_title = forms.CharField(max_length=100, required=False, label="Fonction")

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["job_title"].initial = self.instance.get_recruiter_profile().job_title
        self.helper = FormHelper()
        self.helper.form_tag = False

    def save(self, commit: bool = True) -> User:
        user = super().save(commit=commit)
        if commit:
            profile = user.get_recruiter_profile()
            profile.job_title = self.cleaned_data["job_title"]
            profile.save(update_fields=["job_title"])
        return user


class CompanyInvitationForm(forms.ModelForm):
    class Meta:
        model = CompanyInvitation
        fields = ("email", "role")
        labels = {"email": "Email du recruteur", "role": "Rôle"}

    def __init__(self, *args, company: Company, **kwargs):
        super().__init__(*args, **kwargs)
        self.company = company

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if RecruiterProfile.objects.filter(company=self.company, user__email__iexact=email).exists():
            raise forms.ValidationError("Ce recruteur fait déjà partie de l'entreprise.")
        return email
