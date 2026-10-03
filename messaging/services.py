from django.conf import settings
from django.db import transaction

from core.tasks import send_email_task

from .models import Notification


def notify(recipient, kind: str, title: str, body: str = "", url: str = "", email: bool = True) -> Notification:
    """Create an in-app notification and (optionally) email it after the transaction commits."""
    notification = Notification.objects.create(
        recipient=recipient,
        kind=kind,
        title=title,
        body=body,
        url=url,
    )
    if email and recipient.email:
        link = f"{settings.SITE_URL}{url}" if url else settings.SITE_URL
        message = f"{body}\n\n{link}" if body else link
        transaction.on_commit(lambda: send_email_task.delay(f"[DevHire] {title}", message, [recipient.email]))
    return notification


def notify_company(company, kind: str, title: str, body: str = "", url: str = "", exclude_user=None) -> None:
    """Notify every recruiter of a company."""
    for profile in company.recruiters.select_related("user"):
        if exclude_user is not None and profile.user_id == exclude_user.pk:
            continue
        notify(profile.user, kind, title, body, url)
