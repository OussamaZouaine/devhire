from django.conf import settings
from django.db import models

from applications.models import Application


class Message(models.Model):
    """Message exchanged between the candidate and the recruiters about an application."""

    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_messages",
    )
    body = models.TextField("message")
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"{self.sender} → candidature {self.application_id}"


class Notification(models.Model):
    class Kind(models.TextChoices):
        APPLICATION_RECEIVED = "application_received", "Nouvelle candidature"
        STATUS_CHANGED = "status_changed", "Statut modifié"
        MESSAGE = "message", "Nouveau message"
        INTERVIEW = "interview", "Entretien planifié"
        INVITATION = "invitation", "Invitation"
        JOB_ALERT = "job_alert", "Alerte emploi"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    kind = models.CharField(max_length=30, choices=Kind.choices)
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    url = models.CharField(max_length=255, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["recipient", "is_read"])]

    def __str__(self) -> str:
        return f"{self.recipient}: {self.title}"
