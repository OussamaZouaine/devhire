from django.contrib.auth.models import AbstractUser
from django.db import models

from .validators import validate_file_max_size, validate_pdf_file


def validate_cv_file(file) -> None:
    validate_pdf_file(file)
    validate_file_max_size(file)


def candidate_cv_upload_path(instance: "CandidateProfile", filename: str) -> str:
    return f"cvs/user_{instance.user_id}/{filename}"


class User(AbstractUser):
    class Role(models.TextChoices):
        CANDIDATE = "candidate", "Candidat"
        RECRUITER = "recruiter", "Recruteur"

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.CANDIDATE,
    )

    def __str__(self) -> str:
        return f"{self.username} ({self.get_role_display()})"

    def get_candidate_profile(self) -> "CandidateProfile":
        profile, _ = CandidateProfile.objects.get_or_create(user=self)
        return profile

    def get_recruiter_profile(self) -> "RecruiterProfile":
        profile, _ = RecruiterProfile.objects.get_or_create(
            user=self,
            defaults={"company_name": f"Entreprise de {self.username}"},
        )
        return profile


class CandidateProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="candidateprofile",
    )
    cv = models.FileField(
        upload_to=candidate_cv_upload_path,
        blank=True,
        null=True,
        validators=[validate_cv_file],
        help_text="CV au format PDF uniquement",
    )
    phone = models.CharField(max_length=20, blank=True)
    bio = models.TextField(blank=True)
    skills = models.TextField(
        blank=True,
        help_text="Compétences séparées par des virgules",
    )
    location = models.CharField(max_length=100, blank=True)

    def __str__(self) -> str:
        return f"Profil candidat — {self.user.username}"


class RecruiterProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="recruiterprofile",
    )
    company_name = models.CharField(max_length=200)
    company_logo = models.ImageField(
        upload_to="logos/",
        blank=True,
        null=True,
    )
    company_description = models.TextField(blank=True)
    website = models.URLField(blank=True)

    def __str__(self) -> str:
        return f"{self.company_name} — {self.user.username}"
