"""
Job offer search.

On PostgreSQL the keyword search uses full-text search (SearchVector /
SearchRank with French stemming): "développeurs" matches "développeur" and
results can be ordered by relevance. On SQLite we fall back to icontains.
"""

from django.db import connection
from django.db.models import F, Q, QuerySet
from django.db.models.functions import Coalesce

from .models import JobOffer


def uses_full_text_search() -> bool:
    return connection.vendor == "postgresql"


def _keyword_filter(queryset: QuerySet, query: str) -> QuerySet:
    if uses_full_text_search():
        from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector

        vector = (
            SearchVector("title", weight="A", config="french")
            + SearchVector("skills__name", weight="A", config="french")
            + SearchVector("company__name", weight="B", config="french")
            + SearchVector("description", weight="C", config="french")
        )
        search_query = SearchQuery(query, config="french", search_type="websearch")
        matching_ids = JobOffer.objects.annotate(search=vector).filter(search=search_query).values("pk")
        rank = SearchRank(
            SearchVector("title", weight="A", config="french")
            + SearchVector("description", weight="C", config="french"),
            search_query,
        )
        return queryset.filter(pk__in=matching_ids).annotate(rank=rank)

    return queryset.filter(
        Q(title__icontains=query)
        | Q(description__icontains=query)
        | Q(skills__name__icontains=query)
        | Q(company__name__icontains=query)
    ).distinct()


def search_offers(filters: dict, queryset: QuerySet | None = None) -> QuerySet:
    """Apply the JobSearchForm filters. `filters` only contains non-empty values."""
    queryset = queryset if queryset is not None else JobOffer.objects.open()
    queryset = queryset.select_related("company").prefetch_related("skills")

    if query := filters.get("q"):
        queryset = _keyword_filter(queryset, query)
    if location := filters.get("location"):
        queryset = queryset.filter(location__icontains=location)
    if contract_type := filters.get("contract_type"):
        queryset = queryset.filter(contract_type=contract_type)
    if remote_policy := filters.get("remote_policy"):
        queryset = queryset.filter(remote_policy=remote_policy)
    if experience_level := filters.get("experience_level"):
        queryset = queryset.filter(experience_level=experience_level)
    if salary_min := filters.get("salary_min"):
        queryset = queryset.filter(
            Q(salary_max__gte=salary_min) | Q(salary_max__isnull=True, salary_min__gte=salary_min)
        )
    if skill := filters.get("skill"):
        queryset = queryset.filter(skills__name__iexact=skill)

    sort = filters.get("sort")
    if sort == "salary":
        return queryset.order_by(Coalesce("salary_max", "salary_min").desc(nulls_last=True), "-created_at")
    if sort == "relevance" and filters.get("q") and uses_full_text_search():
        return queryset.order_by(F("rank").desc(), "-created_at")
    return queryset.order_by("-created_at")
