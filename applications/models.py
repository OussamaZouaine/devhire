from django.db import models

from accounts.models import CandidateProfile
from jobs.models import JobOffer


class Application(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "En attente"
        ACCEPTED = "accepted", "Acceptée"
        REJECTED = "rejected", "Refusée"

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
        default=Status.PENDING,
    )
    cover_letter = models.TextField(blank=True)
    applied_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [["candidate", "job_offer"]]
        ordering = ["-applied_at"]

    def __str__(self) -> str:
        return (
            f"{self.candidate.user.username} → {self.job_offer.title} "
            f"({self.get_status_display()})"
        )
