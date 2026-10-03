from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone

from accounts.models import CandidateProfile, Company, RecruiterProfile
from matching.models import Skill


class JobOfferQuerySet(models.QuerySet):
    def open(self):
        """Active offers whose deadline has not passed."""
        today = timezone.localdate()
        return self.filter(is_active=True).filter(models.Q(deadline__isnull=True) | models.Q(deadline__gte=today))


class JobOffer(models.Model):
    class ContractType(models.TextChoices):
        CDI = "CDI", "CDI"
        CDD = "CDD", "CDD"
        STAGE = "Stage", "Stage"
        ALTERNANCE = "Alternance", "Alternance"
        FREELANCE = "Freelance", "Freelance"

    class RemotePolicy(models.TextChoices):
        ONSITE = "onsite", "Sur site"
        HYBRID = "hybrid", "Hybride"
        REMOTE = "remote", "Télétravail complet"

    class ExperienceLevel(models.TextChoices):
        JUNIOR = "junior", "Junior (0-2 ans)"
        MID = "mid", "Confirmé (2-5 ans)"
        SENIOR = "senior", "Senior (5+ ans)"
        LEAD = "lead", "Lead / Expert"

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="job_offers",
    )
    recruiter = models.ForeignKey(
        RecruiterProfile,
        on_delete=models.SET_NULL,
        null=True,
        related_name="job_offers",
        help_text="Recruteur qui a publié l'offre",
    )
    title = models.CharField("titre", max_length=200)
    description = models.TextField()
    location = models.CharField("localisation", max_length=100)
    contract_type = models.CharField(
        "type de contrat",
        max_length=20,
        choices=ContractType.choices,
        default=ContractType.CDI,
    )
    remote_policy = models.CharField(
        "télétravail",
        max_length=20,
        choices=RemotePolicy.choices,
        default=RemotePolicy.ONSITE,
    )
    experience_level = models.CharField(
        "niveau d'expérience",
        max_length=20,
        choices=ExperienceLevel.choices,
        default=ExperienceLevel.JUNIOR,
    )
    skills = models.ManyToManyField(
        Skill,
        blank=True,
        related_name="job_offers",
        verbose_name="compétences requises",
    )
    salary_min = models.PositiveIntegerField("salaire min. (€/an)", blank=True, null=True)
    salary_max = models.PositiveIntegerField("salaire max. (€/an)", blank=True, null=True)
    deadline = models.DateField(
        "date limite de candidature",
        blank=True,
        null=True,
    )
    is_active = models.BooleanField("active", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = JobOfferQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Offre d'emploi"

    def __str__(self) -> str:
        return f"{self.title} — {self.company.name}"

    def get_absolute_url(self) -> str:
        return reverse("jobs:job_offer_detail", kwargs={"pk": self.pk})

    @property
    def skill_names(self) -> list[str]:
        return [skill.name for skill in self.skills.all()]

    @property
    def is_expired(self) -> bool:
        return self.deadline is not None and self.deadline < timezone.localdate()

    @property
    def is_open(self) -> bool:
        return self.is_active and not self.is_expired

    def matching_document(self) -> str:
        return " ".join([self.title, self.description, " ".join(self.skill_names)])

    def can_be_managed_by(self, user) -> bool:
        if not user.is_authenticated or not user.is_recruiter:
            return False
        return user.get_recruiter_profile().company_id == self.company_id


class SavedJob(models.Model):
    candidate = models.ForeignKey(
        CandidateProfile,
        on_delete=models.CASCADE,
        related_name="saved_jobs",
    )
    job_offer = models.ForeignKey(
        JobOffer,
        on_delete=models.CASCADE,
        related_name="saved_by",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["candidate", "job_offer"],
                name="unique_saved_job",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.candidate.user.username} ♥ {self.job_offer.title}"


class JobAlert(models.Model):
    """A saved search; matching new offers are emailed to the candidate."""

    candidate = models.ForeignKey(
        CandidateProfile,
        on_delete=models.CASCADE,
        related_name="job_alerts",
    )
    name = models.CharField("nom de l'alerte", max_length=100)
    query = models.CharField("mots-clés", max_length=200, blank=True)
    location = models.CharField("localisation", max_length=100, blank=True)
    contract_type = models.CharField(
        "type de contrat",
        max_length=20,
        choices=JobOffer.ContractType.choices,
        blank=True,
    )
    remote_policy = models.CharField(
        "télétravail",
        max_length=20,
        choices=JobOffer.RemotePolicy.choices,
        blank=True,
    )
    salary_min = models.PositiveIntegerField("salaire minimum", blank=True, null=True)
    is_active = models.BooleanField("active", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_sent_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Alerte emploi"

    def __str__(self) -> str:
        return f"{self.name} ({self.candidate.user.username})"

    def as_search_params(self) -> dict[str, str]:
        params = {
            "q": self.query,
            "location": self.location,
            "contract_type": self.contract_type,
            "remote_policy": self.remote_policy,
            "salary_min": str(self.salary_min or ""),
        }
        return {key: value for key, value in params.items() if value}


class JobOfferView(models.Model):
    """One row per visitor (session) and per day — used for analytics."""

    job_offer = models.ForeignKey(
        JobOffer,
        on_delete=models.CASCADE,
        related_name="views",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    session_key = models.CharField(max_length=40)
    viewed_on = models.DateField(default=timezone.localdate)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["job_offer", "session_key", "viewed_on"],
                name="unique_offer_view_per_session_per_day",
            ),
        ]
        indexes = [models.Index(fields=["job_offer", "viewed_on"], name="jobs_view_offer_day_idx")]

    def __str__(self) -> str:
        return f"Vue {self.job_offer_id} le {self.viewed_on}"
