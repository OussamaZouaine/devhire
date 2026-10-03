from datetime import UTC

from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from matching.services import match
from messaging.models import Notification
from messaging.services import notify, notify_company

from .models import Application, ApplicationStatusHistory, Interview

CANDIDATE_STATUS_MESSAGES = {
    Application.Status.SHORTLISTED: "Bonne nouvelle : votre candidature a été présélectionnée.",
    Application.Status.INTERVIEW: "Le recruteur souhaite vous rencontrer en entretien.",
    Application.Status.TECHNICAL_TEST: "Vous passez à l'étape du test technique.",
    Application.Status.OFFER: "Le recruteur vous fait une proposition !",
    Application.Status.HIRED: "Félicitations, vous êtes embauché(e) !",
    Application.Status.REJECTED: "Votre candidature n'a malheureusement pas été retenue.",
}


@transaction.atomic
def submit_application(candidate, job_offer, cover_letter: str = "") -> Application:
    application = Application.objects.create(
        candidate=candidate,
        job_offer=job_offer,
        cover_letter=cover_letter,
        match_score=match(candidate, job_offer).score,
    )
    ApplicationStatusHistory.objects.create(
        application=application,
        from_status="",
        to_status=application.status,
        changed_by=candidate.user,
    )
    notify_company(
        job_offer.company,
        Notification.Kind.APPLICATION_RECEIVED,
        f"Nouvelle candidature pour « {job_offer.title} »",
        f"{candidate.user.display_name} a postulé (compatibilité : {application.match_score} %).",
        reverse("applications:application_detail", kwargs={"pk": application.pk}),
    )
    return application


@transaction.atomic
def change_status(application: Application, new_status: str, changed_by, note: str = "") -> bool:
    changed = application.change_status(new_status, changed_by=changed_by, note=note)
    if changed and new_status in CANDIDATE_STATUS_MESSAGES:
        notify(
            application.candidate.user,
            Notification.Kind.STATUS_CHANGED,
            f"« {application.job_offer.title} » : {application.get_status_display()}",
            CANDIDATE_STATUS_MESSAGES[new_status],
            reverse("applications:candidate_application_detail", kwargs={"pk": application.pk}),
        )
    return changed


@transaction.atomic
def withdraw(application: Application) -> None:
    application.change_status(
        Application.Status.WITHDRAWN,
        changed_by=application.candidate.user,
    )
    notify_company(
        application.job_offer.company,
        Notification.Kind.STATUS_CHANGED,
        f"Candidature retirée — {application.job_offer.title}",
        f"{application.candidate.user.display_name} a retiré sa candidature.",
        reverse("applications:application_detail", kwargs={"pk": application.pk}),
    )


@transaction.atomic
def schedule_interview(interview: Interview, scheduled_by) -> Interview:
    interview.created_by = scheduled_by
    interview.save()
    application = interview.application
    early_stages = {Application.Status.RECEIVED, Application.Status.SHORTLISTED}
    if application.status in early_stages:
        application.change_status(Application.Status.INTERVIEW, changed_by=scheduled_by, note="Entretien planifié")
    local_time = timezone.localtime(interview.scheduled_at)
    notify(
        application.candidate.user,
        Notification.Kind.INTERVIEW,
        f"Entretien planifié — {application.job_offer.title}",
        f"Le {local_time:%d/%m/%Y à %H:%M} ({interview.get_mode_display()}). {interview.location}",
        reverse("applications:candidate_application_detail", kwargs={"pk": application.pk}),
    )
    return interview


def _ics_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def interview_to_ics(interview: Interview) -> str:
    """iCalendar (RFC 5545) file so the interview can be added to any calendar."""
    fmt = "%Y%m%dT%H%M%SZ"
    start = interview.scheduled_at.astimezone(UTC)
    end = interview.ends_at.astimezone(UTC)
    created = interview.created_at.astimezone(UTC)
    offer = interview.application.job_offer
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//DevHire//Entretiens//FR",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:interview-{interview.pk}@devhire",
        f"DTSTAMP:{created.strftime(fmt)}",
        f"DTSTART:{start.strftime(fmt)}",
        f"DTEND:{end.strftime(fmt)}",
        f"SUMMARY:{_ics_escape(f'Entretien — {offer.title} ({offer.company.name})')}",
        f"LOCATION:{_ics_escape(interview.location or interview.get_mode_display())}",
        f"DESCRIPTION:{_ics_escape(interview.notes)}",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    return "\r\n".join(lines) + "\r\n"
