"""Statistics for the recruiter dashboard and the public market trends page."""

from datetime import timedelta

from django.db.models import Avg, Count, Min, Q
from django.db.models.functions import TruncDate
from django.utils import timezone

from accounts.models import CandidateProfile, Company
from applications.models import Application, ApplicationStatusHistory
from assessments.models import QuizAttempt
from jobs.models import JobOffer, JobOfferView
from matching.models import Skill

FUNNEL_STAGES = [status for status in Application.PIPELINE if status != Application.Status.REJECTED]


def percent(part: int, total: int) -> float:
    return round(100 * part / total, 1) if total else 0.0


def daily_series(queryset, date_field: str, days: int) -> tuple[list[str], list[int]]:
    """Counts per day for the last `days` days (missing days filled with 0)."""
    today = timezone.localdate()
    start = today - timedelta(days=days - 1)
    if date_field.endswith("_on"):
        rows = queryset.filter(**{f"{date_field}__gte": start}).values(date_field).annotate(n=Count("id"))
        counts = {row[date_field]: row["n"] for row in rows}
    else:
        rows = (
            queryset.filter(**{f"{date_field}__date__gte": start})
            .annotate(day=TruncDate(date_field))
            .values("day")
            .annotate(n=Count("id"))
        )
        counts = {row["day"]: row["n"] for row in rows}
    labels, values = [], []
    for offset in range(days):
        day = start + timedelta(days=offset)
        labels.append(day.strftime("%d/%m"))
        values.append(counts.get(day, 0))
    return labels, values


def funnel(applications) -> list[dict]:
    """How many applications reached each stage of the pipeline (from the history)."""
    stage_index = {status: index for index, status in enumerate(FUNNEL_STAGES)}
    furthest: dict[int, int] = {}
    for application_id, status in applications.values_list("id", "status"):
        furthest[application_id] = stage_index.get(status, 0)
    history = ApplicationStatusHistory.objects.filter(application__in=applications).values_list(
        "application_id", "to_status"
    )
    for application_id, status in history:
        if status in stage_index:
            furthest[application_id] = max(furthest.get(application_id, 0), stage_index[status])
    total = len(furthest)
    result = []
    for index, status in enumerate(FUNNEL_STAGES):
        count = sum(1 for value in furthest.values() if value >= index)
        result.append({"status": status, "label": status.label, "count": count, "percent": percent(count, total)})
    return result


def average_response_days(applications) -> float | None:
    """Average delay between the application and the recruiter's first status change."""
    first_changes = (
        ApplicationStatusHistory.objects.filter(application__in=applications)
        .exclude(from_status="")
        .exclude(to_status=Application.Status.WITHDRAWN)
        .values("application_id", "application__applied_at")
        .annotate(first=Min("changed_at"))
    )
    delays = [
        (row["first"] - row["application__applied_at"]).total_seconds() / 86400 for row in first_changes if row["first"]
    ]
    return round(sum(delays) / len(delays), 1) if delays else None


def company_dashboard(company: Company, days: int = 30) -> dict:
    offers = JobOffer.objects.filter(company=company)
    applications = Application.objects.filter(job_offer__company=company)
    views = JobOfferView.objects.filter(job_offer__company=company)

    total_views = views.count()
    total_applications = applications.count()
    hired = applications.filter(status=Application.Status.HIRED).count()

    per_offer = list(
        offers.annotate(
            view_count=Count("views", distinct=True),
            application_count=Count("applications", distinct=True),
            hired_count=Count(
                "applications",
                filter=Q(applications__status=Application.Status.HIRED),
                distinct=True,
            ),
            avg_match=Avg("applications__match_score"),
        ).order_by("-created_at")
    )
    for offer in per_offer:
        offer.conversion = percent(offer.application_count, offer.view_count)

    view_labels, view_values = daily_series(views, "viewed_on", days)
    _, application_values = daily_series(applications, "applied_at", days)

    status_counts = dict(applications.values_list("status").annotate(n=Count("id")))
    quiz_avg = QuizAttempt.objects.filter(
        application__job_offer__company=company, submitted_at__isnull=False
    ).aggregate(avg=Avg("score"))["avg"]

    return {
        "kpis": {
            "open_offers": offers.open().count(),
            "views": total_views,
            "applications": total_applications,
            "hired": hired,
            "view_to_application": percent(total_applications, total_views),
            "application_to_hire": percent(hired, total_applications),
            "avg_response_days": average_response_days(applications),
            "avg_match": round(applications.aggregate(avg=Avg("match_score"))["avg"] or 0),
            "quiz_avg": round(quiz_avg) if quiz_avg is not None else None,
        },
        "per_offer": per_offer,
        "funnel": funnel(applications),
        "timeline": {"labels": view_labels, "views": view_values, "applications": application_values},
        "status_breakdown": [
            {
                "label": status.label,
                "count": status_counts.get(status.value, 0),
                "color": Application.STATUS_COLORS[status],
            }
            for status in Application.Status
        ],
    }


def market_trends(limit: int = 10) -> dict:
    open_offers = JobOffer.objects.open()
    by_city = list(open_offers.values("location").annotate(n=Count("id")).order_by("-n", "location")[:limit])
    by_contract = list(open_offers.values("contract_type").annotate(n=Count("id")).order_by("-n"))
    contract_labels = dict(JobOffer.ContractType.choices)
    by_remote = list(open_offers.values("remote_policy").annotate(n=Count("id")).order_by("-n"))
    remote_labels = dict(JobOffer.RemotePolicy.choices)

    open_ids = open_offers.values("id")
    demanded = list(
        Skill.objects.annotate(
            demand=Count("job_offers", filter=Q(job_offers__in=open_ids), distinct=True),
            supply=Count("candidates", distinct=True),
        )
        .filter(demand__gt=0)
        .order_by("-demand", "name")[:limit]
    )
    for skill in demanded:
        skill.ratio = round(skill.supply / skill.demand, 1) if skill.demand else None

    salaries = open_offers.filter(salary_min__isnull=False, contract_type=JobOffer.ContractType.CDI)
    salary_by_level = [
        {
            "label": label,
            "avg": round(salaries.filter(experience_level=value).aggregate(avg=Avg("salary_min"))["avg"] or 0),
        }
        for value, label in JobOffer.ExperienceLevel.choices
    ]

    return {
        "totals": {
            "open_offers": open_offers.count(),
            "companies": Company.objects.filter(job_offers__in=open_ids).distinct().count(),
            "candidates": CandidateProfile.objects.count(),
            "applications": Application.objects.count(),
        },
        "by_city": [{"label": row["location"], "count": row["n"]} for row in by_city],
        "by_contract": [
            {"label": contract_labels.get(row["contract_type"], row["contract_type"]), "count": row["n"]}
            for row in by_contract
        ],
        "by_remote": [
            {"label": remote_labels.get(row["remote_policy"], row["remote_policy"]), "count": row["n"]}
            for row in by_remote
        ],
        "top_skills": demanded,
        "salary_by_level": salary_by_level,
    }
