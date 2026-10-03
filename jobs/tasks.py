from celery import shared_task
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from django.utils.http import urlencode

from messaging.models import Notification
from messaging.services import notify

from .models import JobAlert, JobOffer
from .search import search_offers

MAX_OFFERS_PER_ALERT = 10


@shared_task
def send_job_alerts() -> int:
    """Notify each active alert of the offers published since the last run."""
    sent = 0
    now = timezone.now()
    alerts = JobAlert.objects.filter(is_active=True).select_related("candidate__user")
    for alert in alerts:
        since = alert.last_sent_at or alert.created_at
        offers = list(
            search_offers(
                alert.as_search_params(),
                JobOffer.objects.open().filter(created_at__gt=since),
            )[:MAX_OFFERS_PER_ALERT]
        )
        if offers:
            lines = [
                f"- {offer.title} ({offer.company.name}, {offer.location}) : "
                f"{settings.SITE_URL}{offer.get_absolute_url()}"
                for offer in offers
            ]
            notify(
                alert.candidate.user,
                Notification.Kind.JOB_ALERT,
                f"{len(offers)} nouvelle(s) offre(s) pour « {alert.name} »",
                "\n".join(lines),
                f"{reverse('core:home')}?{urlencode(alert.as_search_params())}",
            )
            sent += 1
        alert.last_sent_at = now
        alert.save(update_fields=["last_sent_at"])
    return sent
