import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


@shared_task(autoretry_for=(OSError,), retry_backoff=True, max_retries=3)
def send_email_task(subject: str, message: str, recipients: list[str]) -> int:
    return send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, recipients, fail_silently=False)
