import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from matching.models import Skill

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

    @property
    def display_name(self) -> str:
        return self.get_full_name() or self.username

    @property
    def is_candidate(self) -> bool:
        return self.role == self.Role.CANDIDATE

    @property
    def is_recruiter(self) -> bool:
        return self.role == self.Role.RECRUITER

    def get_candidate_profile(self) -> "CandidateProfile":
        profile, _ = CandidateProfile.objects.get_or_create(user=self)
        return profile

    def get_recruiter_profile(self) -> "RecruiterProfile":
        try:
            return self.recruiterprofile
        except RecruiterProfile.DoesNotExist:
            company = Company.objects.create(name=f"Entreprise de {self.username}")
            return RecruiterProfile.objects.create(
                user=self,
                company=company,
                company_role=RecruiterProfile.CompanyRole.ADMIN,
            )


class Company(models.Model):
    name = models.CharField("nom", max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    logo = models.ImageField("logo", upload_to="logos/", blank=True, null=True)
    description = models.TextField("description", blank=True)
    website = models.URLField("site web", blank=True)
    location = models.CharField("siège", max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Entreprise"

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._unique_slug()
        super().save(*args, **kwargs)

    def _unique_slug(self) -> str:
        base = slugify(self.name) or "entreprise"
        slug = base
        index = 2
        while Company.objects.filter(slug=slug).exclude(pk=self.pk).exists():
            slug = f"{base}-{index}"
            index += 1
        return slug

    def get_absolute_url(self) -> str:
        return reverse("accounts:company_detail", kwargs={"slug": self.slug})


class CandidateProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="candidateprofile",
    )
    headline = models.CharField(
        "titre du profil",
        max_length=120,
        blank=True,
        help_text="Ex. : Développeuse Python / Django",
    )
    years_of_experience = models.PositiveSmallIntegerField(
        "années d'expérience",
        default=0,
    )
    cv = models.FileField(
        upload_to=candidate_cv_upload_path,
        blank=True,
        null=True,
        validators=[validate_cv_file],
        help_text="CV au format PDF uniquement",
    )
    cv_text = models.TextField(
        blank=True,
        editable=False,
        help_text="Texte extrait automatiquement du CV (utilisé pour le matching).",
    )
    phone = models.CharField("téléphone", max_length=20, blank=True)
    bio = models.TextField(blank=True)
    skills = models.ManyToManyField(
        Skill,
        blank=True,
        related_name="candidates",
        verbose_name="compétences",
    )
    location = models.CharField("localisation", max_length=100, blank=True)

    def __str__(self) -> str:
        return f"Profil candidat — {self.user.username}"

    @property
    def skill_names(self) -> list[str]:
        return [skill.name for skill in self.skills.all()]

    def matching_document(self) -> str:
        """All the text describing the candidate, used by the TF-IDF matching."""
        parts = [self.headline, self.bio, " ".join(self.skill_names), self.cv_text]
        parts += [f"{exp.title} {exp.description}" for exp in self.experiences.all()]
        parts += [f"{edu.degree} {edu.field_of_study}" for edu in self.educations.all()]
        return " ".join(part for part in parts if part)

    @property
    def completion_percent(self) -> int:
        checks = [
            bool(self.cv),
            bool(self.headline),
            bool(self.bio),
            bool(self.location),
            self.skills.exists(),
            self.experiences.exists(),
            self.educations.exists(),
        ]
        return round(100 * sum(checks) / len(checks))


class Experience(models.Model):
    candidate = models.ForeignKey(
        CandidateProfile,
        on_delete=models.CASCADE,
        related_name="experiences",
    )
    title = models.CharField("poste", max_length=150)
    company = models.CharField("entreprise", max_length=150)
    start_date = models.DateField("début")
    end_date = models.DateField("fin", blank=True, null=True, help_text="Vide si en cours")
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["-start_date"]
        verbose_name = "Expérience"

    def __str__(self) -> str:
        return f"{self.title} — {self.company}"


class Education(models.Model):
    candidate = models.ForeignKey(
        CandidateProfile,
        on_delete=models.CASCADE,
        related_name="educations",
    )
    school = models.CharField("établissement", max_length=150)
    degree = models.CharField("diplôme", max_length=150)
    field_of_study = models.CharField("domaine", max_length=150, blank=True)
    start_year = models.PositiveSmallIntegerField("année de début")
    end_year = models.PositiveSmallIntegerField("année de fin", blank=True, null=True)

    class Meta:
        ordering = ["-start_year"]
        verbose_name = "Formation"

    def __str__(self) -> str:
        return f"{self.degree} — {self.school}"


class Language(models.Model):
    class Level(models.TextChoices):
        A1 = "A1", "A1 — Débutant"
        A2 = "A2", "A2 — Élémentaire"
        B1 = "B1", "B1 — Intermédiaire"
        B2 = "B2", "B2 — Avancé"
        C1 = "C1", "C1 — Autonome"
        C2 = "C2", "C2 — Maîtrise"
        NATIVE = "native", "Langue maternelle"

    candidate = models.ForeignKey(
        CandidateProfile,
        on_delete=models.CASCADE,
        related_name="languages",
    )
    name = models.CharField("langue", max_length=50)
    level = models.CharField("niveau", max_length=10, choices=Level.choices)

    class Meta:
        ordering = ["name"]
        verbose_name = "Langue"
        constraints = [
            models.UniqueConstraint(
                fields=["candidate", "name"],
                name="unique_language_per_candidate",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.level})"


class RecruiterProfile(models.Model):
    class CompanyRole(models.TextChoices):
        ADMIN = "admin", "Administrateur"
        MEMBER = "member", "Recruteur"

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="recruiterprofile",
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="recruiters",
    )
    company_role = models.CharField(
        "rôle dans l'entreprise",
        max_length=20,
        choices=CompanyRole.choices,
        default=CompanyRole.ADMIN,
    )
    job_title = models.CharField("fonction", max_length=100, blank=True)

    def __str__(self) -> str:
        return f"{self.company.name} — {self.user.username}"

    @property
    def company_name(self) -> str:
        return self.company.name

    @property
    def is_company_admin(self) -> bool:
        return self.company_role == self.CompanyRole.ADMIN


class CompanyInvitation(models.Model):
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="invitations",
    )
    email = models.EmailField()
    role = models.CharField(
        max_length=20,
        choices=RecruiterProfile.CompanyRole.choices,
        default=RecruiterProfile.CompanyRole.MEMBER,
    )
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    invited_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="sent_invitations",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(blank=True, null=True)

    VALIDITY_DAYS = 7

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Invitation {self.email} → {self.company}"

    @property
    def is_expired(self) -> bool:
        return timezone.now() > self.created_at + timezone.timedelta(days=self.VALIDITY_DAYS)

    @property
    def is_pending(self) -> bool:
        return self.accepted_at is None and not self.is_expired

    def get_absolute_url(self) -> str:
        return reverse("accounts:accept_invitation", kwargs={"token": self.token})
