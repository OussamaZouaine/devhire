from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

from accounts.models import CandidateProfile
from jobs.models import JobOffer


class Application(models.Model):
    class Status(models.TextChoices):
        RECEIVED = "received", "Reçue"
        SHORTLISTED = "shortlisted", "Présélectionnée"
        INTERVIEW = "interview", "Entretien"
        TECHNICAL_TEST = "technical_test", "Test technique"
        OFFER = "offer", "Proposition"
        HIRED = "hired", "Embauché(e)"
        REJECTED = "rejected", "Refusée"
        WITHDRAWN = "withdrawn", "Retirée"

    # Columns of the recruiter Kanban board, in order.
    PIPELINE = [
        Status.RECEIVED,
        Status.SHORTLISTED,
        Status.INTERVIEW,
        Status.TECHNICAL_TEST,
        Status.OFFER,
        Status.HIRED,
        Status.REJECTED,
    ]
    CLOSED_STATUSES = {Status.HIRED, Status.REJECTED, Status.WITHDRAWN}
    STATUS_COLORS = {
        Status.RECEIVED: "secondary",
        Status.SHORTLISTED: "info",
        Status.INTERVIEW: "primary",
        Status.TECHNICAL_TEST: "warning",
        Status.OFFER: "dark",
        Status.HIRED: "success",
        Status.REJECTED: "danger",
        Status.WITHDRAWN: "light",
    }

    candidate = models.ForeignKey(
        CandidateProfile,
        on_delete=models.CASCADE,
        related_name="applications",
    )
    job_offer = models.ForeignKey(
        JobOffer,
        on_delete=models.CASCADE,
        related_name="applications",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.RECEIVED,
    )
    cover_letter = models.TextField(blank=True)
    match_score = models.PositiveSmallIntegerField(
        "score de compatibilité",
        blank=True,
        null=True,
        help_text="Calculé au moment de la candidature (0-100).",
    )
    applied_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-applied_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["candidate", "job_offer"],
                name="unique_application_per_offer",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.candidate.user.username} → {self.job_offer.title} ({self.get_status_display()})"

    @property
    def status_color(self) -> str:
        return self.STATUS_COLORS.get(self.status, "secondary")

    @property
    def is_closed(self) -> bool:
        return self.status in self.CLOSED_STATUSES

    @property
    def can_be_withdrawn(self) -> bool:
        return not self.is_closed

    def change_status(self, new_status: str, changed_by=None, note: str = "") -> bool:
        """Update the status, record the history entry. Returns False if unchanged."""
        if new_status == self.status:
            return False
        if new_status not in self.Status.values:
            raise ValueError(f"Statut inconnu : {new_status}")
        previous = self.status
        self.status = new_status
        self.save(update_fields=["status", "updated_at"])
        ApplicationStatusHistory.objects.create(
            application=self,
            from_status=previous,
            to_status=new_status,
            changed_by=changed_by,
            note=note,
        )
        return True


class ApplicationStatusHistory(models.Model):
    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name="history",
    )
    from_status = models.CharField(max_length=20, choices=Application.Status.choices, blank=True)
    to_status = models.CharField(max_length=20, choices=Application.Status.choices)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    note = models.CharField(max_length=255, blank=True)
    changed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["changed_at"]
        verbose_name = "Historique de statut"

    def __str__(self) -> str:
        return f"{self.application_id}: {self.from_status} → {self.to_status}"


class RecruiterNote(models.Model):
    """Private note — visible only to the recruiters of the company."""

    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name="notes",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
    )
    content = models.TextField("note")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Note sur {self.application_id}"


class Interview(models.Model):
    class Mode(models.TextChoices):
        VIDEO = "video", "Visioconférence"
        ONSITE = "onsite", "Sur place"
        PHONE = "phone", "Téléphone"

    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name="interviews",
    )
    scheduled_at = models.DateTimeField("date et heure")
    duration_minutes = models.PositiveSmallIntegerField("durée (minutes)", default=45)
    mode = models.CharField("format", max_length=20, choices=Mode.choices, default=Mode.VIDEO)
    location = models.CharField(
        "lieu ou lien",
        max_length=255,
        blank=True,
        help_text="Adresse, lien de visio ou numéro de téléphone",
    )
    notes = models.TextField("informations pour le candidat", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["scheduled_at"]
        verbose_name = "Entretien"

    def __str__(self) -> str:
        return f"Entretien {self.application} le {self.scheduled_at:%d/%m/%Y %H:%M}"

    @property
    def ends_at(self):
        return self.scheduled_at + timedelta(minutes=self.duration_minutes)

    @property
    def is_upcoming(self) -> bool:
        return self.scheduled_at >= timezone.now()
